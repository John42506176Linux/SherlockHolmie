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
                cur.execute("CREATE INDEX IF NOT EXISTS post_data_index ON reddit_posts USING hnsw (embeddings vector_cosine_ops) WITH (m = 36, ef_construction = 500);")
                log.info("Adding subreddit_data_index")
                cur.execute("CREATE INDEX IF NOT EXISTS subreddit_data_index ON subreddit USING hnsw (embeddings vector_cosine_ops) WITH (m = 16, ef_construction = 200);")
                log.info("Adding time_index")
                cur.execute("CREATE INDEX IF NOT EXISTS time_index ON reddit_posts (created_utc);")
                log.info("Adding body_fts index")
                cur.execute("CREATE INDEX IF NOT EXISTS body_fts ON reddit_posts USING gin (fts);")

                log.info("Committing changes")
                cur.commit()
            except Exception as e:
                log.error(f"Error occurred: {e}")
                cur.rollback()
            finally:
                cur.close()
                log.info("Connection closed")

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

    def insert_users(self, authors):
        try:
            author_objects = []
            for author in tqdm(authors, desc='Fetching authors'):
                author_objects.append(RedditUser.get_user_object(author))
            serialized_author_objects = [user.serialize() for user in author_objects]
            stmt = insert(RedditUser).values(serialized_author_objects)
            stmt = stmt.on_conflict_do_update(
                index_elements=['username'],
                set_={
                    'subreddit_interactions': stmt.excluded.subreddit_interactions,
                    'extracted_user_info': stmt.excluded.extracted_user_info,
                    'description': stmt.excluded.description,
                    'author_flairs': stmt.excluded.author_flairs
                }
            )
            self.db.execute(stmt)
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            log.error(f"Error occurred: {e}")
            raise Exception(e)
    def close(self):
        self.db.rollback()
        self.db.close()