from langchain_openai import OpenAIEmbeddings
import math
import numpy as np
import time
import pyarrow.parquet as pq
from tqdm import tqdm
from models.models import RedditPost
from datetime import datetime
from managers.databaseManager import DatabaseManager
import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

class RedditEmbedder:
    def __init__(self, db_manager: DatabaseManager, model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120):
        self.log = logging.getLogger("bot")
        self.embeddings = OpenAIEmbeddings(model=model, dimensions=dimensions, show_progress_bar=show_progress_bar, max_retries=max_retries, retry_max_seconds=retry_max_seconds)
        self.db_manager = db_manager

    @staticmethod
    def process_embedding(bs):
        # Decode byte strings to strings and convert to numpy arrays
        return np.array(bs, dtype=np.float32)

    def process_chunk_and_append_to_file(self, chunk):
        # Assuming 'combined_text' is the column to embed
        texts = chunk['combined_text'].tolist()
        embedding_list = self.embeddings.embed_documents(texts)

        # Convert the list of embeddings into a DataFrame
        chunk['embeddings'] = [self.process_embedding(embedding) for embedding in embedding_list]
        self.log.info("Processing embedding")
        start_time =  time.time()
        try:
            posts = []
            for index, post in chunk.iterrows():
                reddit_post = RedditPost(
                    id=post['id'],
                    author=post['author'],
                    created_utc=datetime.fromtimestamp(post['created_utc']),
                    permalink=post['permalink'],
                    score=post['score'],
                    body=post['body'],
                    combined_text=post['combined_text'],
                    embeddings=post['embeddings'],
                    num_comments=post['num_comments'],
                    subreddit_name=post['subreddit'],
                    link_id=post['link_id'],
                    parent_id=post['parent_id'],
                    is_post=post['is_post'],
                    archived=post['archived'],
                    title=post['title']
                )
                posts.append(reddit_post)
            
            serialized_posts = [post.serialize() for post in posts]
            self.log.info("Serialize posts")
            stmt = insert(RedditPost).values(serialized_posts)
            stmt = stmt.on_conflict_do_update(
                index_elements=['id'],
                set_={
                    'score': stmt.excluded.score,
                    'num_comments': stmt.excluded.num_comments,
                    'archived': stmt.excluded.archived
                }
            )
            self.log.info("Inserting posts")
            self.db_manager.db.execute(stmt)
            self.db_manager.db.commit()
            self.log.info(f"Elapsed Time:{time.time()-start_time}")
            self.log.info("Posts inserted")
            self.log.info("Documents embedded and added successfully")
        except IntegrityError as e:
            self.db_manager.db.rollback()
            self.log.error(f"INTEGRITY ERROR WHEN Inserting documents:"[0:500])
            raise Exception(e)
        except Exception as e:
            self.db_manager.db.rollback()
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