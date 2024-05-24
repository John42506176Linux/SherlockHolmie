from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean,Table
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB, insert
from pgvector.sqlalchemy import Vector
from sqlalchemy.exc import IntegrityError
import datetime
from tunnelManager import tunnel_manager
import os
from typing import List
import requests
import logging.handlers
from dataDownloader import user_agents
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


Base = declarative_base()


class DatabaseManager:
    def __init__(self):
        self.connection_string = ""
        if os.getenv('ENV') != 'PROD':
            tunnel_manager.start_tunnel()
            self.connection_string = generate_connection_string('127.0.0.1', tunnel_manager.server.local_bind_port)
        else:
            self.connection_string = generate_connection_string(db_host, db_port)
        self.engine = create_engine(self.connection_string, pool_size=10, connect_args={'options': '-c lock_timeout=3000'})
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


association_table = Table(
    "user_subreddit_table",
    Base.metadata,
    Column("subreddit_id", ForeignKey("subreddit.subreddit_name"), primary_key=True),
    Column("reddit_user_username", ForeignKey("reddit_user.username"), primary_key=True),
)


class Subreddit(Base):
    __tablename__ = 'subreddit'
    subreddit_name: Mapped[str] = mapped_column(String(255), primary_key=True,)
    subreddit_description: Mapped[str] = mapped_column(String, nullable=True)
    created_utc: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    language: Mapped[str] = mapped_column(String(255), nullable=True)
    subscribers: Mapped[int] = mapped_column(Integer, nullable=True)
    embeddings: Mapped[Vector] = mapped_column(Vector(1024),nullable=True)
    posts: Mapped[List["RedditPost"]] = relationship("RedditPost", back_populates="subreddit")
    users: Mapped[List["RedditUser"]] =  relationship(
        secondary=association_table, back_populates="subreddits"
    )


class RedditUser(Base):
    __tablename__ = 'reddit_user'
    username: Mapped[str] = mapped_column(String,primary_key=True)
    subreddit_interactions: Mapped[JSONB] = mapped_column(JSONB,nullable=True)
    extracted_user_info:Mapped[JSONB] = mapped_column(JSONB,nullable=True)
    description:Mapped[str] = mapped_column(String,nullable=True)
    author_flairs:Mapped[JSONB] = mapped_column(JSONB,nullable=True)
    subreddits: Mapped[List["Subreddit"]] = relationship("Subreddit",secondary=association_table, back_populates="users")
    posts: Mapped[List["RedditPost"]] = relationship("RedditPost", back_populates="user")

    def serialize(self):
        return {
            "username": self.username,
            "subreddit_interactions": self.subreddit_interactions,
            "extracted_user_info": self.extracted_user_info,
            'author_flairs': self.author_flairs,
            "description": self.description
        }

    @staticmethod
    def get_user_object(author):
        return RedditUser(
            username=author,
            description='',
            extracted_user_info={},
            subreddit_interactions={},
            author_flairs={}
        )
    @staticmethod
    def get_user_interactions(author):
        retry_count = 0
        while retry_count <= 5:
            try:
                subreddit_interaction_url = f"https://arctic-shift.photon-reddit.com/api/user_interactions/subreddits?author={author}"
                response = requests.get(subreddit_interaction_url)
                
                if response.status_code == 400:
                    error_data = response.json()
                    if 'error' in error_data  and 'not supported' in error_data['error']:
                        log.error(f"Author: {author} not supported for interaction data")
                        return None
                    else:
                        log.error(f'400 error for Author {author}: error:{error_data}')
                        return None
                if response.status_code == 429:
                    log.info("Rate limit exceeded. Waiting before retrying.")
                    retry_count += 1
                    if retry_count > 5:  # Max retry attempts
                        log.error("Max retry attempts reached. Exiting.")
                        return None
                    # Exponential backoff
                    wait_time = min(2 ** retry_count, 360)  # Limit wait time to 360 seconds (6 minutes)
                    log.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue  # Retry the request
                response.raise_for_status()  # Raise HTTPError for non-200 status codes
                data = response.json()
                if 'error' in data or 'data' not in data:
                    raise Exception(data.get('error', 'No data returned'))
                return data['data']
            except Exception as e:
                log.error(f"Interaction Data for user {author} Error: {e}")
        return None
    @staticmethod
    def get_user_flairs(author):
        retry_count = 0
        while retry_count <= 5:
            try:
                subreddit_interaction_url = f"https://arctic-shift.photon-reddit.com/api/users/aggregate_flairs?author={author}"
                response = requests.get(subreddit_interaction_url)
                if response.status_code == 400:
                    error_data = response.json()
                    if 'error' in error_data  and 'not supported' in error_data['error']:
                        log.error(f"Author: {author} not supported for interaction data")
                        return None
                    else:
                        log.error(f'400 error for Author {author}: error:{error_data}')
                        return None
                if response.status_code == 429:
                    log.info("Rate limit exceeded. Waiting before retrying.")
                    retry_count += 1
                    if retry_count > 5:  # Max retry attempts
                        log.error("Max retry attempts reached. Exiting.")
                        return None
                    # Exponential backoff
                    wait_time = min(2 ** retry_count, 360)  # Limit wait time to 360 seconds (6 minutes)
                    log.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue  # Retry the request
                response.raise_for_status()  # Raise HTTPError for non-200 status codes
                data = response.json()
                if 'error' in data or 'data' not in data:
                    raise Exception(data.get('error', 'No data returned'))
                return data['data']
            except Exception as e:
                log.error(f"Interaction Data for user {author} Error: {e}")
        return None
    
    @staticmethod
    def get_user_description(author):
        retries = 0
        max_retries = 5
        while retries <= max_retries:
            response = None
            try:
                url = f"https://www.reddit.com/u/{author}/about.json"
                user_agent = random.choice(user_agents)
                # Set the headers
                headers = {'User-Agent': user_agent}
                response = requests.get(url, headers=headers)
                if response.status_code == 200:
                    data = response.json()
                    return data['data']['subreddit']['public_description']
                elif response.status_code == 404:
                    log.error(f"Author {author} not found (404).")
                    return None
                elif response.status_code == 429:
                    log.error(f"Rate Limit on fetching user description for {author}")
                    retries += 1
                    if retries > max_retries:
                        log.error("Max retry attempts reached. Exiting.")
                        return None
                    # Exponential backoff
                    wait_time = min(2 ** retries, 360)  # Limit wait time to 360 seconds (6 minutes)
                    log.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            except Exception as e:
                log.error(f"Request Error fetching user description: {e}")
                return None
        return None


class RedditPost(Base):
    __tablename__ = 'reddit_posts'
    id: Mapped[str] = mapped_column(String, primary_key=True)
    author: Mapped[str] = mapped_column(ForeignKey('reddit_user.username'))
    score: Mapped[int] = mapped_column(Integer,nullable=True)
    created_utc: Mapped[datetime.datetime] = mapped_column(DateTime)
    permalink: Mapped[str] = mapped_column(String(1024))
    body: Mapped[str] = mapped_column(String)
    subreddit_name: Mapped[str] = mapped_column(ForeignKey('subreddit.subreddit_name'))
    parent_id: Mapped[str] = mapped_column(String,nullable=True)
    link_id: Mapped[str] = mapped_column(String,nullable=True)
    is_post: Mapped[bool] = mapped_column(Boolean)
    archived: Mapped[bool] = mapped_column(Boolean,nullable=True)
    title: Mapped[str] = mapped_column(String,nullable=True)
    num_comments: Mapped[int] = mapped_column(Integer,nullable=True)
    combined_text: Mapped[str] = mapped_column(String,nullable=True)
    embeddings: Mapped[Vector] = mapped_column(Vector(256),nullable=True)

    user:Mapped["RedditUser"] = relationship("RedditUser",back_populates="posts")
    subreddit: Mapped["Subreddit"] = relationship("Subreddit", back_populates="posts")

    def serialize(self):
        return {
            "id": self.id,
            "author": self.author,
            "score": self.score,
            "created_utc": self.created_utc.isoformat() if self.created_utc else None,
            "permalink": self.permalink,
            "body": self.body,
            "subreddit_name": self.subreddit_name,
            "parent_id": self.parent_id,
            "link_id": self.link_id,
            "is_post": self.is_post,
            "archived": self.archived,
            "title": self.title,
            "num_comments": self.num_comments,
            "combined_text": self.combined_text,
            "embeddings": self.embeddings.tolist() if self.embeddings is not None else None
        }