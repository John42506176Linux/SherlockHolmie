import time
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from sentence_transformers import SentenceTransformer
from sentence_transformers.quantization import quantize_embeddings
from pydantic import BaseModel
from typing import Union, List
import uvicorn
import batched

app = FastAPI()

# Load both models
large_model = SentenceTransformer('mixedbread-ai/mxbai-embed-large-v1')
xsmall_model = SentenceTransformer('mixedbread-ai/mxbai-embed-xsmall-v1')

# Enable dynamic batching for both models
large_model.encode = batched.dynamically(large_model.encode)
xsmall_model.encode = batched.dynamically(xsmall_model.encode)

class EmbeddingsRequest(BaseModel):
    input: Union[List[str], List[List[str]]]
    quantize: bool = False
    quantize_format: str = "binary"
    dimensions: int = 512
    model_size: str = "large"  # Options: "large" or "xsmall"

MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

@app.post("/embeddings", response_class=ORJSONResponse)
def embeddings(request: EmbeddingsRequest):
    """
    Generate embeddings for the provided input strings.

    Args:
        request (EmbeddingsRequest): The request containing input strings, model selection, and quantization options.

    Returns:
        dict: A dictionary containing the generated embeddings and binarized embeddings separately.
    """
    total_start_time = time.time()
    
    # Step 1: Model Selection
    step1_start = time.time()
    model = large_model if request.model_size == "large" else xsmall_model
    step1_time = time.time() - step1_start
    print(f"Model selection time: {step1_time:.4f} seconds")

    # Step 2: Input Type Check
    step2_start = time.time()
    is_nested = isinstance(request.input, list) and all(isinstance(i, list) for i in request.input)
    step2_time = time.time() - step2_start
    print(f"Input type checking time: {step2_time:.4f} seconds")

    if is_nested:
        # Step 3: Flatten the Input
        step3_start = time.time()
        flattened_input = [item for sublist in request.input for item in sublist]
        step3_time = time.time() - step3_start
        print(f"Flattening input time: {step3_time:.4f} seconds")

        # Step 4: Encode All Inputs with Retries
        step4_start = time.time()
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                embeddings = model.encode(flattened_input)
                break
            except Exception as e:
                print(f"Attempt {attempt} - Error during encoding embeddings: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    return ORJSONResponse({"error": "Failed to generate embeddings after multiple retries."}, status_code=500)
        step4_time = time.time() - step4_start
        print(f"Encoding embeddings time: {step4_time:.4f} seconds")

        # Step 5: Truncate Embeddings
        step5_start = time.time()
        truncated_embeddings = [embedding[:request.dimensions] for embedding in embeddings]
        step5_time = time.time() - step5_start
        print(f"Truncating embeddings time: {step5_time:.4f} seconds")

        # Step 6: Quantize Embeddings (if required)
        step6_start = time.time()
        binarized_embeddings = None
        if request.quantize:
            try:
                binarized_embeddings = quantize_embeddings(truncated_embeddings, precision=request.quantize_format)
            except Exception as e:
                print(f"Error during quantization: {e}")
                return ORJSONResponse({"error": "Failed to quantize embeddings."}, status_code=500)
        step6_time = time.time() - step6_start
        print(f"Quantizing embeddings time: {step6_time:.4f} seconds")

        # Step 7: Split Embeddings Back to Nested Structure
        step7_start = time.time()
        split_embeddings = []
        split_binarized = [] if request.quantize else None
        index = 0
        for sublist in request.input:
            sub_embeddings = truncated_embeddings[index: index + len(sublist)]
            split_embeddings.append(sub_embeddings)
            if request.quantize:
                sub_binarized = binarized_embeddings[index: index + len(sublist)]
                split_binarized.append(sub_binarized)
            index += len(sublist)
        step7_time = time.time() - step7_start
        print(f"Splitting embeddings time: {step7_time:.4f} seconds")

        # Step 8: Assemble Response Data
        step8_start = time.time()
        response_data = {"embeddings": split_embeddings}
        if request.quantize:
            response_data["binarized_embeddings"] = split_binarized
        step8_time = time.time() - step8_start
        print(f"Assembling response data time: {step8_time:.4f} seconds")
    else:
        # Handle flat list input

        # Step 3: Encode All Inputs with Retries
        step3_start = time.time()
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                embeddings = model.encode(request.input)
                break
            except Exception as e:
                print(f"Attempt {attempt} - Error during encoding embeddings: {e}")
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
                else:
                    return ORJSONResponse({"error": "Failed to generate embeddings after multiple retries."}, status_code=500)
        step3_time = time.time() - step3_start
        print(f"Encoding embeddings time: {step3_time:.4f} seconds")

        # Step 4: Truncate Embeddings
        step4_start = time.time()
        truncated_embeddings = [embedding[:request.dimensions] for embedding in embeddings]
        step4_time = time.time() - step4_start
        print(f"Truncating embeddings time: {step4_time:.4f} seconds")

        # Step 5: Quantize Embeddings (if required)
        step5_start = time.time()
        binarized_embeddings = None
        if request.quantize:
            try:
                binarized_embeddings = quantize_embeddings(truncated_embeddings, precision=request.quantize_format)
            except Exception as e:
                print(f"Error during quantization: {e}")
                return ORJSONResponse({"error": "Failed to quantize embeddings."}, status_code=500)
        step5_time = time.time() - step5_start
        print(f"Quantizing embeddings time: {step5_time:.4f} seconds")

        # Step 6: Assemble Response Data
        step6_start = time.time()
        response_data = {"embeddings": truncated_embeddings}
        if request.quantize:
            response_data["binarized_embeddings"] = binarized_embeddings
        step6_time = time.time() - step6_start
        print(f"Assembling response data time: {step6_time:.4f} seconds")

    total_time = time.time() - total_start_time
    print(f"Total processing time: {total_time:.4f} seconds")
    
    return ORJSONResponse(response_data)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)