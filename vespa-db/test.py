import subprocess
import json
import time
import requests  # Add this import
from typing import Iterable, Dict
from vespa.io import VespaResponse
from datetime import datetime, timezone
from typing import List
import time

API_URL = "http://ec2-35-89-68-7.us-west-2.compute.amazonaws.com:8000/embeddings"  # Update with your FastAPI URL

def generate_embedding(text: List[str], model_size: str = "large", quantize: bool = False, quantize_format: str = "binary") -> List:
    payload = {
        "input": text,
        "model_size": model_size,
        "quantize": quantize,
        "quantize_format": quantize_format,
        "dimensions": 512  # Adjust as needed
    }
    response = requests.post(API_URL, json=payload)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Error generating embeddings: {response.text}")
        return []

def assign_embeddings(documents: List[Dict]) -> List[Dict]:
    """
    Generate and assign all required embeddings to each document.

    Args:
        documents (List[Dict]): List of document dictionaries to assign embeddings to.
    """
    # Collect all texts for each embedding field
    titles = [doc["title"] for doc in documents]
    bodies = [doc["body"] for doc in documents]
    keywords = [doc["keywords"] for doc in documents]  # List of lists

    # Generate embeddings in bulk
    print("Generating title_mrl_bq_embeddings (xsmall, 64, no quantize)...")
    start_time = time.time()
    title_response = generate_embedding(
        titles,
        model_size="large",
        quantize=True,
    )
    print(f"Time taken: {time.time() - start_time:.2f} seconds")
    
    start_time = time.time()
    print("Generating body_embedding (large, 512, no quantize)...")
    body_embedding_response = generate_embedding(
        bodies,
        model_size="large",
        quantize=True,
    )
    print(f"Time taken: {time.time() - start_time:.2f} seconds")

    start_time = time.time()
    print("Generating keyword_embeddings (xsmall, large, quantize)...")
    keyword_response = generate_embedding(
        keywords,
        model_size="large",
        quantize=True,
        quantize_format="binary",
    )
    print(f"Time taken: {time.time() - start_time:.2f} seconds")

    # Assign embeddings back to documents
    print("Assigning embeddings to documents...")
    for idx, doc in enumerate(documents):
        doc['body_embedding'] = body_embedding_response['embeddings'][idx]
        doc['mrl_bq_embedding'] = body_embedding_response['binarized_embeddings'][idx]
        doc['title_embedding'] = title_response['embeddings'][idx]
        doc['title_mrl_bq_embeddings'] = title_response['binarized_embeddings'][idx]
        doc['keyword_embeddings'] = keyword_response['embeddings'][idx]
        doc['keyword_mrl_bq_embeddings'] = keyword_response['binarized_embeddings'][idx]
    
    print("Embeddings assigned successfully!")
    return documents


    

if __name__ == "__main__":
    # Example documents
    documents = [
        {
            "reddit_id": f"lndon8j_{i}",
            "link_id": f"t3_1fhywfi_{i}",
            "subreddit_name": "LocalLLM",
            "title": "Mac or PC?",
            "author": "swiftninja_",
            "created_utc": datetime.now(timezone.utc),
            "url": f"/r/LocalLLM/comments/1fhywfi_{i}/",
            "body": "Who's money? If it's your own, then Mac.",
            "score": 3,
            "num_comments": -1,
            "is_post": False,
            "parent_post": "I'm planning to set up inference with LLMs...",
            "archived": True,
            "keywords": ["mac", "money", "company"],
        }
        for i in range(10000)
    ]

    # Assign embeddings to documents
    assign_embeddings(documents)
