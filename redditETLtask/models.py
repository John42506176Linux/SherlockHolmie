from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey,Table,Computed
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Mapped, mapped_column
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import JSONB,insert,TSVECTOR
from pgvector.sqlalchemy import Vector
from sqlalchemy.exc import IntegrityError
import datetime
import psycopg2
from tunnelManager import tunnel_manager
import os
from typing import List
import requests
import logging.handlers
from dataDownloader import get_user_description,get_user_interactions,user_agents
import time
from tqdm import tqdm
import random 

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

db_username = os.getenv('DB_USERNAME')
db_password=os.getenv('DB_PASSWORD')
db_host=os.getenv('DB_HOST')
db_port=os.getenv('DB_PORT')
db_database=os.getenv('DB_DATABASE')

# Connect to the database and create the extension
def generate_connection_string(host,port):
    return  f"postgresql://{db_username}:{db_password}@{host}:{port}/{db_database}"

Base = declarative_base()
connection_string = ""
if os.getenv('ENV') != 'PROD':
    tunnel_manager.start_tunnel()  
    connection_string = generate_connection_string('127.0.0.1',tunnel_manager.server.local_bind_port)
else:
    connection_string = generate_connection_string(db_host,db_port)   
engine = create_engine(connection_string,pool_size=10,connect_args={'options': '-c lock_timeout=3000'})
Session = sessionmaker(bind=engine)
db = Session()

# not sqlalchemy.orm.mapped_column
association_table = Table(
    "user_subreddit_table",
    Base.metadata,
    Column("subreddit_id", ForeignKey("subreddit.subreddit_name"),primary_key=True),
    Column("reddit_user_username", ForeignKey("reddit_user.username"),primary_key=True),
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
    
def serialize_reddit_user(reddit_user):
    return {
        "username": reddit_user.username,
        "subreddit_interactions": reddit_user.subreddit_interactions,
        "extracted_user_info": reddit_user.extracted_user_info,
        'author_flairs' : reddit_user.author_flairs,
        "description": reddit_user.description
    }

def initialize_database():
    log.info("Starting connecting")
    with engine.connect() as cur:
        log.info("Connecting to postgres");
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        log.info("Create db call")
        Base.metadata.create_all(engine, checkfirst=True)
        log.info("Meta data created")
        try:
            log.info("Altering table to add FTS column")
            cur.execute("ALTER TABLE reddit_posts ADD COLUMN IF NOT EXISTS fts tsvector GENERATED ALWAYS AS (to_tsvector('english', body)) STORED;")
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

def insert_subreddit_info():
    subreddit_name = os.getenv('SUBREDDIT')
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
            # Exponential backoff
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
        db.add(subreddit)
        db.commit()
        db.refresh(subreddit)
    except IntegrityError as e:
        if 'duplicate' in str(e):
            log.info('Duplicate Subreddit download')
            db.rollback()
            # Duplicate entry, update instead
            existing_subreddit = db.query(Subreddit).filter(Subreddit.subreddit_name == subreddit_name).first()
            if existing_subreddit and data:
                existing_subreddit.subreddit_description = data['data'][0]['public_description']
                existing_subreddit.created_utc = datetime.datetime.fromtimestamp(data['data'][0]['created_utc'], datetime.timezone.utc)
                existing_subreddit.language = data['data'][0]['lang']
                existing_subreddit.subscribers = int(data['data'][0]['subscribers'])
                db.commit()
            return  # Exit the function upon successful update
        else:
            log.error(f"SQL Integrity Error: {e}")
            db.rollback()
            return 
    except Exception as e:
        log.error(f"Unexpected error inserting subreddit info: {e}")
        return

def insert_users(authors):
    try:
        author_objects = []
        for author in tqdm(authors, desc='Fetching authors'):
            author_objects.append(get_user_object(author))
        serialized_author_objects = [serialize_reddit_user(user) for user in author_objects]
        stmt = insert(RedditUser).values(serialized_author_objects)
        stmt = stmt.on_conflict_do_update(
            index_elements=['username'],
            set_={
                'subreddit_interactions': stmt.excluded.subreddit_interactions,
                'extracted_user_info': stmt.excluded.extracted_user_info,
                'description': stmt.excluded.description,
                'author_flairs' : stmt.excluded.author_flairs
            }
        )
        db.execute(stmt)
        db.commit()
    except Exception as e:
        db.rollback()
        log.error(f"Error occurred: {e}")
        raise Exception(e)
        
def get_user_object(author):
    user = RedditUser(
        username=author,
        ## TODO: Getting user data is slow and painful right now, need to think of better methods for this one
        description='', # get_user_description(author),
        extracted_user_info={}, # TODO: Figure out how to do this
        subreddit_interactions={}, # get_user_interactions(author),
        author_flairs = {}
    )
    return user
