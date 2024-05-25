from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean,Table
from sqlalchemy.orm import relationship, Mapped, mapped_column,declarative_base
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector
import datetime
from typing import List
import requests
from downloaders.redditDownloader import user_agents
import time
import random
import logging.handlers

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

Base = declarative_base()

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