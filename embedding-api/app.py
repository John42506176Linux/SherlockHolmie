from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from sentence_transformers import SentenceTransformer
from sentence_transformers.quantization import quantize_embeddings
from pydantic import BaseModel
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
    input: str | list[str]
    quantize: bool = False
    quantize_format:str = "binary"
    model_size: str = "large"  # Options: "large" or "xsmall"

@app.post("/embeddings")
def embeddings(request: EmbeddingsRequest):
    # Select the model based on the request
    model = large_model if request.model_size == "large" else xsmall_model
    
    # Encode the input
    embeddings = model.encode(request.input)
    
    # Optionally quantize the embeddings
    if request.quantize:
        embeddings = quantize_embeddings(embeddings, format=request.quantize_format)
    
    return ORJSONResponse({"embeddings": embeddings})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7998)