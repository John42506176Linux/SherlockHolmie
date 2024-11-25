from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from sentence_transformers import SentenceTransformer
from sentence_transformers.quantization import quantize_embeddings
from pydantic import BaseModel
import uvicorn
import batched
from typing import List, Union
from pydantic import BaseModel

app = FastAPI()

# Load both models
large_model = SentenceTransformer('mixedbread-ai/mxbai-embed-large-v1')
xsmall_model = SentenceTransformer('mixedbread-ai/mxbai-embed-xsmall-v1')

# Enable dynamic batching for both models
large_model.encode = batched.dynamically(large_model.encode)
xsmall_model.encode = batched.dynamically(xsmall_model.encode)



class EmbeddingsRequest(BaseModel):
    input: Union[List[str],List[List[str]]]
    quantize: bool = False
    quantize_format: str = "binary"
    dimensions: int = 512
    model_size: str = "large"  # Options: "large" or "xsmall"  # Options: "large" or "xsmall"

@app.post("/embeddings", response_class=ORJSONResponse)
def embeddings(request: EmbeddingsRequest):
    """
    Generate embeddings for the provided input strings.

    Args:
        request (EmbeddingsRequest): The request containing input strings, model selection, and quantization options.

    Returns:
        dict: A dictionary containing the generated embeddings and binarized embeddings separately.
    """
    # Select the model based on the request
    model = large_model if request.model_size == "large" else xsmall_model

    # Determine if the input is a list of lists
    is_nested = isinstance(request.input, list) and all(isinstance(i, list) for i in request.input)

    if is_nested:
        # Flatten the list of lists
        flattened_input = [item for sublist in request.input for item in sublist]
        # Encode all inputs at once
        embeddings = model.encode(flattened_input)
        # Truncate embeddings
        truncated_embeddings = [embedding[:request.dimensions] for embedding in embeddings]

        # Optionally quantize the embeddings
        binarized_embeddings = None
        if request.quantize:
            binarized_embeddings = quantize_embeddings(truncated_embeddings, precision=request.quantize_format)

        # Split the embeddings back to the original nested structure
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

        response_data = {"embeddings": split_embeddings}
        if request.quantize:
            response_data["binarized_embeddings"] = split_binarized
    else:
        # Handle flat list input
        embeddings = model.encode(request.input)
        truncated_embeddings = [embedding[:request.dimensions] for embedding in embeddings]

        # Optionally quantize the embeddings
        binarized_embeddings = None
        if request.quantize:
            binarized_embeddings = quantize_embeddings(truncated_embeddings, precision=request.quantize_format)

        response_data = {"embeddings": truncated_embeddings}
        if request.quantize:
            response_data["binarized_embeddings"] = binarized_embeddings

    return ORJSONResponse(response_data)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)