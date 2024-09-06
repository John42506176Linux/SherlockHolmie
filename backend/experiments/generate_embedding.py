from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv(override=True)
# Initialize the embedding model
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120)
query = "Discussions about cash advances and credit building"
print(f"Embedding:{embeddings.embed_query(query)}")