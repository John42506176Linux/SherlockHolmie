from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from sentence_transformers import SentenceTransformer
from sentence_transformers.quantization import quantize_embeddings
from pydantic import BaseModel
import uvicorn
import batched
from typing import List
from pydantic import BaseModel

app = FastAPI()

# Load both models
large_model = SentenceTransformer('mixedbread-ai/mxbai-embed-large-v1')
xsmall_model = SentenceTransformer('mixedbread-ai/mxbai-embed-xsmall-v1')

# Enable dynamic batching for both models
large_model.encode = batched.dynamically(large_model.encode)
xsmall_model.encode = batched.dynamically(xsmall_model.encode)



class EmbeddingsRequest(BaseModel):
    input: List[str]
    quantize: bool = False
    quantize_format: str = "binary"
    dimensions: int = 512
    model_size: str = "large"  # Options: "large" or "xsmall"  # Options: "large" or "xsmall"

@app.post("/embeddings")
def embeddings(request: EmbeddingsRequest):
    print("INPUT TYPE: ", type(request.input))
    print("INPUT: ", request.input)
    # Select the model based on the request
    model = large_model if request.model_size == "large" else xsmall_model
    
    # Encode the input
    embeddings = model.encode(request.input)
    truncated_embeddings = [embedding[:request.dimensions] for embedding in embeddings]
    
    # Optionally quantize the embeddings
    binarized_embeddings = None
    if request.quantize:
        binarized_embeddings = quantize_embeddings(truncated_embeddings, precision=request.quantize_format)
    
    return ORJSONResponse({"embeddings": truncated_embeddings, "binarized_embeddings": binarized_embeddings})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7998)