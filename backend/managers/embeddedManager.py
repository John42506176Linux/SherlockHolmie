from keybert.backend import BaseEmbedder
import requests
import os
from tqdm import tqdm
import numpy as np
from keybert import KeyBERT
from keyphrase_vectorizers import KeyphraseCountVectorizer
import weaviate
import os
import logging
import weaviate.classes as wvc
from weaviate.util import generate_uuid5
import datetime
from datetime import datetime, timezone
from utilities.utils import embed_documents
from tenacity import retry, stop_after_attempt
import time
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.config import ConnectionConfig


log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

class CustomEmbedder(BaseEmbedder):
    def __init__(self, model_name,dimensions=512):
        super().__init__()
        self.model_name = model_name
        self.dimensions = dimensions

    def embed(self, documents, verbose=False):
        embeddings = embed_documents(self.model_name,documents,dimensions=self.dimensions)
        return embeddings
    

class KeywordManager():
    def __init__(self):
        self.custom_embedder = CustomEmbedder(model_name=os.getenv('AWS_EMBEDDING_MODEL'))
        self.custom_kw_model = KeyBERT(model=self.custom_embedder)
        self.vectorizer = KeyphraseCountVectorizer()

    def get_keywords(self, documents,doc_embeddings=None,word_embeddings=None):
        try:
            keywords = self.custom_kw_model.extract_keywords(documents,doc_embeddings=doc_embeddings,word_embeddings=word_embeddings, vectorizer=self.vectorizer,use_mmr=True,diversity=0.5)
            self.keywords = keywords
            return keywords
        except Exception as e:
            print(f"Error extracting keywords: {e}")
            return []

    def embed_keywords(self):
        keyword_strs = []
        for kw in self.keywords:
            keyword_strs.append(', '.join([item[0] for item in kw]))
        return self.custom_embedder.embed(keyword_strs)

class WeaviateManager():
    def __init__(self):
        self.keywords_manager = KeywordManager()
        self.embedder = CustomEmbedder(model_name=os.getenv('AWS_EMBEDDING_MODEL'))
        URL = os.getenv("WCS_URL")
        APIKEY = os.getenv("WCS_API_KEY")
        # Connect to a WCS instance
        self.client = weaviate.connect_to_wcs(
                cluster_url=URL,
                auth_credentials=weaviate.auth.AuthApiKey(APIKEY),
                additional_config=AdditionalConfig(
                    connection=ConnectionConfig(
                        session_pool_connections=30,
                        session_pool_maxsize=200,
                        session_pool_max_retries=3,
                    ),
                    timeout=Timeout(init=1440, query=1440, insert=1440)  # Values in seconds
                )
            )
        self.reddit_collection = self.client.collections.get("RedditDB")
    
    def bulk_insert_weaviate(self, posts):
        # Assuming posts is a list of dictionaries
        log.info("Embedding posts")
        post_bodies = [f"{post['body']}" for post in posts]
        log.info("Extracting post embeddings")
        start_time = time.time()
        posts_vectors,word_embeddings = self.keywords_manager.custom_kw_model.extract_embeddings(post_bodies,vectorizer=self.keywords_manager.vectorizer)
        log.info(f"Elapsed Time for post embedding: {time.time()-start_time}")
        log.info("Extracting title embeddings")
        start_time = time.time()
        title_vectors = self.embedder.embed([f"{post['title']}" for post in posts])
        log.info(f"Elapsed Time for title embedding: {time.time()-start_time}")
        # posts
        log.info("Getting keywords")
        start_time =  time.time()
        keywords = self.keywords_manager.get_keywords(post_bodies,doc_embeddings=posts_vectors,word_embeddings=word_embeddings)
        log.info(f"Elapsed Time for keyword extraction: {time.time()-start_time}")
        log.info("Embedding keywords")
        start_time = time.time()
        keyword_vectors = self.keywords_manager.embed_keywords()
        log.info(f"Elapsed Time for keyword embedding: {time.time()-start_time}")
        log.info("Inserting into Weaviate")
        
        property_rows = [
            {
                "title": post['title'],
                "body": post['body'],
                "parent_post": post['parent_post'],
                "num_comments": post['num_comments'],
                "author": post['author'],
                "subreddit_name": post['subreddit'],
                "permalink": post['permalink'],
                "created_utc": datetime.fromtimestamp(post['created_utc'], tz=timezone.utc).isoformat(),
                "is_post": post['is_post'],
                "archived": post['archived'],
                "score": post['score'],
                "link_id": post['link_id'],
                "parent_id": post['parent_id'],
                "parent_post": post['parent_post'],
                "reddit_id": post['id'],
                "keywords" : ', '.join([item[0] for item in keyword]),
            } for post,keyword in zip(posts,keywords)
        ]
        start_time = time.time()

        with self.reddit_collection.batch.fixed_size(batch_size=50)as batch:
            for i, data_row in enumerate(property_rows):
                batch.add_object(
                    properties=data_row,
                    vector={
                        "title_vector": title_vectors[i],
                        "posts_vector": posts_vectors[i],
                        "keywords_vector": keyword_vectors[i],
                    },
                    uuid=generate_uuid5(data_row['reddit_id'])
                )
        failed_objs_a = self.reddit_collection.batch.failed_objects
        if failed_objs_a:
            log.info(f"Number of failed objects in the first batch: {len(failed_objs_a)}")
            for i, failed_obj in enumerate(failed_objs_a, 1):
                log.info(f"Failed object {i}:")
                log.info(f"Error message: {failed_obj.message}")
        log.info(f"Num Errors: {batch.number_errors}")
        log.info(f"Elapsed Insertion Time:{time.time()-start_time}")
        log.info("Batch completed")


