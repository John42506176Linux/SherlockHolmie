from pathlib import Path
import requests

def download_model(model_name: str = "mixedbread-ai/mxbai-rerank-xsmall-v1") -> None:
    """Download the ONNX model from HuggingFace."""
    url = f"https://huggingface.co/{model_name}/resolve/main/onnx/model_quantized.onnx"
    local_model_path = "models/model_quantized.onnx"

    try:
        r = requests.get(url)
        r.raise_for_status()
        
        Path(local_model_path).parent.mkdir(parents=True, exist_ok=True)
        with open(local_model_path, "wb") as f:
            f.write(r.content)
        print(f"Downloaded model to {local_model_path}")
    except Exception as e:
        print(f"Error downloading model: {e}")

def download_tokenizer(model_name: str = "mixedbread-ai/mxbai-rerank-xsmall-v1") -> None:
    """Download the tokenizer files from HuggingFace."""
    base_url = f"https://huggingface.co/{model_name}/resolve/main"
    files = ["tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"]
    
    try:
        for file in files:
            url = f"{base_url}/{file}"
            local_path = f"models/{file}"
            
            r = requests.get(url)
            r.raise_for_status()
            
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(r.content)
            print(f"Downloaded {file} to {local_path}")
    except Exception as e:
        print(f"Error downloading tokenizer: {e}")

if __name__ == "__main__":
    download_model()