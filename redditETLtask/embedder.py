from langchain_openai import OpenAIEmbeddings
import math
import numpy as np
import time
import pyarrow.parquet as pq
from tqdm import tqdm
from models.models import RedditPost
from datetime import datetime
from models.models import DatabaseManager
import logging
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

# Configure logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

# Initialize the embedding model
embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120)

def process_embedding(bs):
    # Decode byte strings to strings and convert to numpy arrays
    return np.array(bs, dtype=np.float32)

def process_chunk_and_append_to_file(chunk):
    # Assuming 'combined_text' is the column to embed
    texts = chunk['combined_text'].tolist()
    embedding_list = embeddings.embed_documents(texts)

    # Convert the list of embeddings into a DataFrame
    chunk['embeddings'] = [process_embedding(embedding) for embedding in embedding_list]
    log.info("Processing embedding")
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
        log.info("Serialize posts")
        stmt = insert(RedditPost).values(serialized_posts)
        stmt = stmt.on_conflict_do_update(
            index_elements=['id'],
            set_={
                'score': stmt.excluded.score,
                'num_comments': stmt.excluded.num_comments,
                'archived': stmt.excluded.archived
            }
        )
        log.info("Inserting posts")
        db_manager.db.execute(stmt)
        db_manager.db.commit()
        log.info(f"Elapsed Time:{time.time()-start_time}")
        log.info("Posts inserted")
        log.info("Documents embedded and added successfully")
    except IntegrityError as e:
        db_manager.db.rollback()
        log.error(f"INTEGRITY ERROR WHEN Inserting documents:"[0:500])
        raise Exception(e)
    except Exception as e:
        db_manager.db.rollback()
        log.error(f"Error occurred Inserting Batch Documents: {e}"[0:500])


def bulk_embed_posts(db_manager:DatabaseManager):
    chunksize = 10000  # Adjust based on your memory constraints
    parquet_file = pq.ParquetFile('reddit_data_filtered.parquet')
    start_time = time.time()

    # Start processing from the last checkpoint
    file_metadata = parquet_file.metadata
    total_rows = file_metadata.num_rows
    total_batches = math.ceil(total_rows / chunksize)
    log.info(f"NUM ROWS:{total_rows}")

    # Start processing from the last checkpoint
    batches = parquet_file.iter_batches(batch_size=chunksize)
    log.info(f"Total Batches:{total_batches}")
    for batch_index, batch in enumerate(tqdm(batches, desc="Processing and appending chunks", initial=0, total=total_batches)):
        log.info("Processing RecordBatch")
        batch_df = batch.to_pandas()
        process_chunk_and_append_to_file(batch_df)

    log.info(f"Elapsed Time: {time.time() - start_time}")

if __name__ == '__main__':
    db_manager = DatabaseManager()
    try:
        log.info("Starting Embedding")
        bulk_embed_posts(db_manager)
        db_manager.db.close()
    except Exception as e:
        log.error(f'ERROR embedding reddit data:{e}'[0:500])
        db_manager.db.rollback()
        db_manager.db.close()
        raise Exception(e)