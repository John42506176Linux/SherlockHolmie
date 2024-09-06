import math
import numpy as np
import time
import pyarrow.parquet as pq
from tqdm import tqdm
from managers.embeddedManager import CustomEmbedder
import logging
from sqlalchemy.dialects.postgresql import insert
from managers.weaviateDBManager import WeaviateManager
import os

class RedditEmbedder:
    def __init__(self, wv_manager: WeaviateManager, model= os.getenv('AWS_EMBEDDING_MODEL'), dimensions=512, show_progress_bar=True, max_retries=5, retry_max_seconds=120):
        self.log = logging.getLogger("bot")
        self.embedder = CustomEmbedder(model_name=model,dimensions=dimensions)
        self.wv_manager = wv_manager

    @staticmethod
    def process_embedding(bs):
        # Decode byte strings to strings and convert to numpy arrays
        return np.array(bs, dtype=np.float32)

    def process_chunk_and_append_to_file(self, chunk):
        # Assuming 'combined_text' is the column to embed
        self.log.info("Processing embedding")
        start_time =  time.time()
        try:
            posts = []
            for index, post in chunk.iterrows():
                properies = {
                    'id': post['id'],
                    'author': post['author'],
                    'created_utc': post['created_utc'],
                    'permalink': post['permalink'],
                    'score': post['score'],
                    'body': post['body'],
                    'num_comments': post['num_comments'],
                    'subreddit': post['subreddit'],
                    'link_id': post['link_id'],
                    'parent_id': post['parent_id'],
                    'is_post': post['is_post'],
                    'archived': post['archived'],
                    'parent_post': post['parent_post'],
                    'title': post['title'],
                }
                posts.append(properies)
            self.wv_manager.bulk_insert_weaviate(posts)
        
            self.log.info(f"Elapsed Time:{time.time()-start_time}")
            self.log.info("Posts inserted")
            self.log.info("Documents embedded and added successfully")
        except Exception as e:
            self.log.error(f"Error occurred Inserting Batch Documents: {e}"[0:500])

    def bulk_embed_posts(self):
        chunksize = 10000  # Adjust based on your memory constraints
        parquet_file = pq.ParquetFile('reddit_data_filtered.parquet')
        start_time = time.time()

        # Start processing from the last checkpoint
        file_metadata = parquet_file.metadata
        total_rows = file_metadata.num_rows
        total_batches = math.ceil(total_rows / chunksize)
        self.log.info(f"NUM ROWS:{total_rows}")

        # Start processing from the last checkpoint
        batches = parquet_file.iter_batches(batch_size=chunksize)
        self.log.info(f"Total Batches:{total_batches}")
        for batch_index, batch in enumerate(tqdm(batches, desc="Processing and appending chunks", initial=0, total=total_batches)):
            self.log.info("Processing RecordBatch")
            batch_df = batch.to_pandas()
            self.process_chunk_and_append_to_file(batch_df)

        self.log.info(f"Elapsed Time: {time.time() - start_time}")