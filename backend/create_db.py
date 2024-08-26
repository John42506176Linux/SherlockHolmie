import weaviate
import os
import logging.handlers
from dotenv import load_dotenv
from managers.databaseManager import DatabaseManager
import weaviate.classes as wvc
import requests
import json

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()
# Set these environment variables
URL = os.getenv("WCS_URL")
APIKEY = os.getenv("WCS_API_KEY")
  
# Connect to a WCS instance
client = weaviate.connect_to_wcs(
cluster_url=URL,
auth_credentials=weaviate.auth.AuthApiKey(APIKEY))

try :
    collection = client.collections.create(
        name="RedditDB",
        description="Reddit database",
        vectorizer_config=[
            wvc.config.Configure.NamedVectors.none(
                name="keywords_vector",
                vector_index_config=wvc.config.Configure.VectorIndex.hnsw(  # Or `flat` or `dynamic`
                distance_metric=wvc.config.VectorDistances.COSINE,
                quantizer=wvc.config.Configure.VectorIndex.Quantizer.bq(),
            ),
            ),
            wvc.config.Configure.NamedVectors.none(
                name="posts_vector",
                vector_index_config=wvc.config.Configure.VectorIndex.hnsw(  # Or `flat` or `dynamic`
                distance_metric=wvc.config.VectorDistances.COSINE,
                quantizer=wvc.config.Configure.VectorIndex.Quantizer.bq(),
            ),
            ),
            wvc.config.Configure.NamedVectors.none(
                name="title_vector",
                vector_index_config=wvc.config.Configure.VectorIndex.hnsw(  # Or `flat` or `dynamic`
                distance_metric=wvc.config.VectorDistances.COSINE,
                quantizer=wvc.config.Configure.VectorIndex.Quantizer.bq(),
            ),
            ),
        ],
        properties=[
            wvc.config.Property(name="keywords", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="post", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="parent_post", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="title", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="num_comments", data_type=wvc.config.DataType.NUMBER),
            wvc.config.Property(name="author", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="subreddit_name", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="permalink", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="created_utc", data_type=wvc.config.DataType.DATE),
            wvc.config.Property(name="is_post", data_type=wvc.config.DataType.BOOL),
            wvc.config.Property(name="archived", data_type=wvc.config.DataType.BOOL),
            wvc.config.Property(name="score", data_type=wvc.config.DataType.NUMBER),
            wvc.config.Property(name="link_id", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="parent_id", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="reddit_id", data_type=wvc.config.DataType.TEXT),
            wvc.config.Property(name="body", data_type=wvc.config.DataType.TEXT),
        ],
    )
except Exception as e:
    log.error(f"Error creating collection: {e}")
finally:
    client.close()