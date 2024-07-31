from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
import datetime
from managers.tunnelManager import TunnelManager
from models.models import Subreddit, RedditUser, Base
import os
import requests
import logging.handlers
from downloaders.redditDownloader import user_agents
import time
from tqdm import tqdm
import random
from sqlalchemy.exc import OperationalError
from sqlalchemy import text
from langchain_openai import OpenAIEmbeddings
from concurrent.futures import ThreadPoolExecutor, as_completed
import psycopg2
from psycopg2 import sql


log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

db_username = os.getenv('DB_USERNAME')
db_password = os.getenv('DB_PASSWORD')
db_host = os.getenv('DB_HOST')
db_port = os.getenv('DB_PORT')
db_database = os.getenv('DB_DATABASE')


def generate_connection_string(host, port):
    return f"postgresql://{db_username}:{db_password}@{host}:{port}/{db_database}"

class DatabaseManager:
    def __init__(self):
        self.connection_string = ""
        if os.getenv('ENV') != 'PROD':
            tunnel_manager = TunnelManager()
            tunnel_manager.start_tunnel()
            self.connection_string = generate_connection_string('127.0.0.1', tunnel_manager.server.local_bind_port)
        else:
            self.connection_string = generate_connection_string(db_host, db_port)
        self.engine = create_engine(self.connection_string, pool_size=10)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def initialize_database(self):
        log.info("Starting connecting")
        with self.engine.connect() as cur:
            log.info("Connecting to postgres")
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            log.info("Create db call")
            Base.metadata.create_all(self.engine, checkfirst=True)
            log.info("Meta data created")
            try:
                log.info("Altering table to add FTS column")
                cur.execute("ALTER TABLE reddit_posts ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (to_tsvector(body)) STORED;")
                log.info("Adding post_data_index")
                cur.execute("CREATE INDEX IF NOT EXISTS post_data_index ON reddit_posts USING hnsw (embeddings vector_cosine_ops) WITH (m = 16, ef_construction = 64);")
                log.info("Adding subreddit_data_index")
                cur.execute("CREATE INDEX IF NOT EXISTS subreddit_data_index ON subreddit USING hnsw (embeddings vector_cosine_ops) WITH (m = 16, ef_construction = 64);")
                log.info("Adding time_index")
                cur.execute("CREATE INDEX IF NOT EXISTS time_index ON reddit_posts (created_utc);")
                log.info("Adding body_fts index")
                cur.execute("CREATE INDEX IF NOT EXISTS body_fts ON reddit_posts USING gin (fts);")

                log.info("Committing changes")
                cur.commit()
            except Exception as e:
                log.error(f"Error occurred Initializing Database: {e}")
                cur.rollback()
            finally:
                cur.close()
                log.info("Connection closed")

    
    def _generate_vector_query(self,space,threshold=0.55):
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120)
        query_embedding = embeddings.embed_query(space)
        vector_search_query = f"""
        SELECT similarity, subreddit_name, permalink, created_utc, author, combined_text, body,is_post,score,archived,id
        FROM (
            SELECT 1 - (embeddings <=> '{query_embedding}') AS similarity,
                subreddit_name, permalink, created_utc, author, combined_text, body,is_post,score,archived,id
            FROM reddit_posts
        ) subquery
        WHERE similarity > {threshold}
        ORDER BY similarity DESC
        LIMIT 200000;
        """
        return vector_search_query

    def _generate_fast_vector_query(self,space,threshold=0.55):
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120)
        query_embedding = embeddings.embed_query(space)
        vector_search_query = f"""
        SET hnsw.ef_search = 1000;
        SELECT similarity, subreddit_name, permalink, created_utc, author, combined_text, body,is_post,score,archived,id
        FROM (
            SELECT (embeddings <=> '{query_embedding}') AS similarity,
                subreddit_name, permalink, created_utc, author, combined_text, body,is_post,score,archived,id
            FROM reddit_posts
        ) subquery
        WHERE similarity < {1-threshold}
        ORDER BY similarity DESC
        LIMIT 200000;
        """
        return vector_search_query
    
    def _generate_keyword_semantic_query(company,space,filter_value=0.10):
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120)
        query_embedding = embeddings.embed_query(space)
        filter_value = filter_value if filter_value else 0.30
        vector_search_query = query = f"""
            SELECT (1 - (keyword_filtered.embeddings <=> '{query_embedding}')) AS similarity,subreddit_name, permalink, created_utc, author,combined_text,body,is_post,score,archived
            FROM (
                SELECT combined_text, subreddit_name, permalink, body, created_utc, author, embeddings,is_post,score,archived
                    (1 - (embeddings <=> '{query_embedding}')) AS similarity
                FROM reddit_posts
                WHERE fts @@ phraseto_tsquery('english','{company}')
                ORDER BY created_utc DESC
                LIMIT 200000
            ) AS keyword_filtered
            WHERE similarity > {filter_value}
            ORDER BY similarity DESC
        """
        return vector_search_query
    
    def _generate_keyword_query(company):
        return f"""
                SELECT combined_text,subreddit_name, permalink, body,created_utc,author,is_post,score,archived
                FROM reddit_posts
                WHERE fts @@ phraseto_tsquery('english','{company}')
                ORDER BY created_utc DESC
                LIMIT 200000;
            """
    
    def space_search_query(self,space,threshold=0.55):
        with psycopg2.connect(self.connection_string, options="-c statement_timeout=0") as conn:
            with conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor) as cur:
                log.info("Connected")
                # Define your query
                sql_query = self._generate_vector_query(space,threshold)
                query = sql.SQL(sql_query)
                start_time=time.time()

                # Execute the query
                cur.execute(query)
                log.info("Executed")
                log.info(f"Execute Time:{time.time()-start_time}")
                # Fetch all the rows
                rows = cur.fetchall()
                log.info(len(rows))
                return rows
    
    def search_multiple_queries(self,queries, hyde_docs,  threshold=0.55):
        def execute_query(hyde_doc, query):
            result = self.space_search_query(hyde_doc, threshold)
            return result, query

        results = {}
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_to_query = {executor.submit(execute_query, hyde_doc, query): query 
                            for hyde_doc, query in zip(hyde_docs, queries)}
            
            for future in as_completed(future_to_query):
                try:
                    rows, query = future.result()
                    for row in rows:
                        item_id = row['id']
                        if item_id not in results or row['similarity'] > results[item_id]['similarity']:
                            results[item_id] = row
                            results[item_id]['best_query'] = query
                except Exception as e:
                    log.error(f"Error with query {future_to_query[future]}: {e}")
                    

        # Convert the dictionary to a list and sort by similarity in descending order
        sorted_results = sorted(results.values(), key=lambda x: x['similarity'], reverse=False)
        
        return sorted_results

    def company_keyword_query(self,company,space=None,filter_value=None):
        # Define your query
        sql_query = None
        if space is None:
            sql_query = self._generate_keyword_query(company)
        else:
            sql_query = self._generate_keyword_semantic_query(company,space,filter_value)
        # Execute the query
        try:
            # Execute the query
            rows = self.db.execute(text(sql_query)).fetchall()
            return rows
        except Exception as e:
            log.error(f"Error occurred: {e}")
            return None

    def insert_subreddit_info(self, subreddit_name):
        retries = 0
        max_retries = 5
        data = None
        while retries <= max_retries:
            try:
                url = f"https://arctic-shift.photon-reddit.com/api/subreddits/search?subreddit={subreddit_name}"
                response = requests.get(url, headers={'User-agent': random.choice(user_agents)})
                response.raise_for_status()
                data = response.json()
                break
            except requests.exceptions.RequestException as e:
                log.error(f"Error fetching subreddit description: {e}")
                retries += 1
                if retries > max_retries:
                    log.error("Max retry attempts reached. Exiting.")
                    break
                wait_time = min(2 ** retries, 360)  # Limit wait time to 360 seconds (6 minutes)
                log.info(f"Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
            except Exception as e:
                log.error(f"Unexpected error getting subreddit info: {e}")
                return
        try:
            subreddit = None
            if data:
                subreddit = Subreddit(
                    subreddit_name=subreddit_name,
                    subreddit_description=data['data'][0]['public_description'],
                    created_utc=datetime.datetime.fromtimestamp(data['data'][0]['created_utc'], datetime.timezone.utc),
                    language=data['data'][0]['lang'],
                    subscribers=int(data['data'][0]['subscribers']),
                )
            else:
                subreddit = Subreddit(
                    subreddit_name=subreddit_name,
                )
            self.db.add(subreddit)
            self.db.commit()
            self.db.refresh(subreddit)
        except IntegrityError as e:
            if 'duplicate' in str(e):
                log.info('Duplicate Subreddit download')
                self.db.rollback()
                existing_subreddit = self.db.query(Subreddit).filter(Subreddit.subreddit_name == subreddit_name).first()
                if existing_subreddit and data:
                    existing_subreddit.subreddit_description = data['data'][0]['public_description']
                    existing_subreddit.created_utc = datetime.datetime.fromtimestamp(data['data'][0]['created_utc'], datetime.timezone.utc)
                    existing_subreddit.language = data['data'][0]['lang']
                    existing_subreddit.subscribers = int(data['data'][0]['subscribers'])
                    self.db.commit()
                return
            else:
                log.error(f"SQL Integrity Error: {e}")
                self.db.rollback()
                return
        except Exception as e:
            log.error(f"Unexpected error inserting subreddit info: {e}")
            return
    
    def insert_users(self, authors, batch_size=10000, retries=3):
            try:
                author_objects = []
                for author in tqdm(authors, desc='Fetching authors'):
                    author_objects.append(RedditUser.get_user_object(author))
                serialized_author_objects = [user.serialize() for user in author_objects]

                for i in range(0, len(serialized_author_objects), batch_size):
                    batch = serialized_author_objects[i:i + batch_size]
                    self._execute_with_retry(batch, retries)

            except Exception as e:
                self.db.rollback()
                log.error(f"Error occurred Inserting Users Into Databse: {e}")
                raise Exception(e)

    def _execute_with_retry(self, batch, retries):
        stmt = insert(RedditUser).values(batch)
        stmt = stmt.on_conflict_do_update(
            index_elements=['username'],
            set_={
                'subreddit_interactions': stmt.excluded.subreddit_interactions,
                'extracted_user_info': stmt.excluded.extracted_user_info,
                'description': stmt.excluded.description,
                'author_flairs': stmt.excluded.author_flairs
            }
        )
        for attempt in range(retries):
            try:
                self.db.execute(stmt)
                self.db.commit()
                return
            except OperationalError as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise e
            except Exception as e:
                self.db.rollback()
                log.error(f"Error occurred: {e}")
                raise Exception(e)
            
    def close(self):
        self.db.rollback()
        self.db.close()