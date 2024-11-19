import os
import logging
from dotenv import load_dotenv
from utilities.utils import embed_documents
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
from managers.keywordManager import KeywordManager
from managers.embeddedManager import CustomEmbedder
from vespa.application import Vespa
from vespa.io import VespaResponse, VespaQueryResponse
from dataclasses import dataclass
from typing import Callable, Optional, Iterable, Dict
import asyncio
import json
import subprocess

@dataclass
class FeedParams:
    name: str
    num_docs: int
    max_connections: int
    function_name: str
    max_workers: Optional[int] = None
    max_queue_size: Optional[int] = None
    num_concurrent_requests: Optional[int] = None


@dataclass
class FeedResult(FeedParams):
    feed_time: Optional[float] = None
import time



log = logging.getLogger("VespaManager")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv(override=True)

class VespaManager:
    def __init__(self):
        self.url = os.getenv("VESPA_URL")
        self.document_type = "reddit_post"
        self.keywords_manager = KeywordManager()
        self.app =  Vespa(url=self.url)

    def close(self):
        log.info("Closing Vespa client")
    
    @staticmethod
    def doc_to_jsonl(doc):
        jsonl_doc = {
            "put": f'id:pyvespa-feed:reddit_post::{doc["reddit_id"]}',
            "fields": {
                "reddit_id": doc["reddit_id"],
                "link_id": doc["link_id"],
                "subreddit_name": doc["subreddit_name"],
                "title": doc["title"],
                "author": doc["author"],
                "created_utc": doc["created_utc"],
                "url": doc["url"],
                "body": doc["body"],
                "score": doc["score"],
                "num_comments": doc["num_comments"],
                "is_post": doc["is_post"],
                "parent_post": doc["parent_post"],
                "archived": doc["archived"],
                "keywords": doc["keywords"],
            }
        }
        return json.dumps(jsonl_doc)

    @staticmethod
    def json_to_file(name, documents):
        # Create the JSONL file
        with open(name, 'w') as f:
            for doc in documents:
                jsonl_line = VespaManager.doc_to_jsonl(doc)  # Updated to use class name
                f.write(jsonl_line + '\n')
    @staticmethod
    def feed_to_vespa(file_name):
        command = f"vespa feed --target {os.getenv('VESPA_URL')} {file_name}"
        try:
            subprocess.run(command, shell=True, check=True)
            print(f"Successfully fed {file_name} to Vespa.")
        except subprocess.CalledProcessError as e:
            print(f"Error feeding {file_name} to Vespa: {e}")

    async def feed(self, posts):
        # Assuming posts is a list of dictionaries
        log.info("Getting keywords")
        post_bodies = [post['body'] for post in posts]
        start_time =  time.time()
        keywords = self.keywords_manager.get_keywords(post_bodies)
        log.info(f"Elapsed Time for keywords: {time.time()-start_time}")
        # We use a semaphore to limit the number of concurrent requests, this is useful to avoid
        # running into memory issues when feeding a large number of documents
        log.info("Feeding to Vespa")
        start_time = time.time()
        documents = []
        for doc, keyword in zip(posts, keywords):
            keyword_list = None
            if isinstance(keyword, list):
                keyword_list = [key[0] for key in keyword]
            else:
                keyword_list = [keyword[0]]
            print
            documents.append({
                "reddit_id": doc["reddit_id"],
                "link_id": doc["link_id"],
                "subreddit_name": doc["subreddit_name"],
                "title": doc["title"],
                "author": doc["author"],
                "created_utc": doc["created_utc"],
                "body": doc["body"],
                "score": doc["score"],
                "num_comments": doc["num_comments"],
                "is_post": doc["is_post"],
                "parent_post": doc["parent_post"],
                "archived": doc["archived"],
                "keywords": keyword_list,
                "url": doc["url"],
            })
        VespaManager.json_to_file("reddit_posts.jsonl", documents)
        VespaManager.feed_to_vespa("reddit_posts.jsonl")
        end_time = time.time()
        log.info(f"Elapsed Feed Time:{end_time-start_time}")   

    

    def query(self,query,hits=500):
        """Perform a semantic search query."""
        with self.app.syncio(connections=10, compress="auto") as session:
            response: VespaQueryResponse = session.query(
                hits=hits,
                body={
                    "yql": "select * from reddit_post where (userQuery()) or ({targetHits:5000}nearestNeighbor(body_embedding,q)) or ({targetHits:5000}nearestNeighbor(mrl_bq_embedding,q_binary)) or ({targetHits:5000}nearestNeighbor(title_embedding,q)) or ({targetHits:5000}nearestNeighbor(keyword_embeddings,q))",
                    "query": query,
                    "queryProfile": 'largeQueryProfile',
                    "ranking": "weighted_closeness_combination",
                    "timeout": "1000s",
                    "input.query(q)": "embed(mxbai,@query)",
                    "input.query(q_binary)": "embed(mxbai,@query)",
                },
            )
            reddit_documents = {}
            for hit in response.hits:
                fields = hit['fields']
                filtered_fields = {k: v for k, v in fields.items() if k not in ['documentid', 'sddocname', 'matchfeatures']}
                filtered_fields['relevance'] = hit['relevance']
                fields['title'] = fields.get('title', '')
                created_utc_dt = datetime.fromtimestamp(fields['created_utc'], tz=timezone.utc)
                reddit_documents[fields['reddit_id']] = {
                    'title': fields['title'],
                    'body': fields['body'],
                    'relevance_score': hit['relevance'],
                    'keywords': fields['keywords'],
                    'author': fields['author'],
                    'subreddit_name': fields['subreddit_name'],
                    'created_utc': created_utc_dt,
                    'permalink': fields['url'],
                    'id' : fields['reddit_id'],
                    'num_comments': fields['num_comments'],
                    'is_post': fields['is_post'],
                    'archived': fields['archived'],
                    'score': fields['score']
                }
            sorted_results = sorted(reddit_documents.items(), key=lambda x: x[1]['relevance_score'], reverse=True)
            return sorted_results

    def get_subreddits(self):
        if not self.app:
            log.error("Vespa client is not initialized.")
            return []
        try:
            with self.app.syncio() as session:
                response: VespaQueryResponse = session.query(
                    yql="select * from reddit_post where true | all(group(subreddit_name) each(output(count())))",
                    hits=0,
                    summary='minimal',
                )
                data = response.hits
                print(data)
                subreddit_names = [
                child['value']
                for group in data
                for subgroup in group.get('children', [])
                if subgroup['label'] == 'subreddit_name'
                for child in subgroup.get('children', [])
                ]
                return subreddit_names
        except Exception as e:
            log.error(f"Error getting subreddits: {e}")
            return []


    def get_latest_subreddit_time(self, subreddit):
        if not self.app:
            log.error("Vespa client is not initialized.")
            return None

        try:
            with self.app.syncio() as session:
                response: VespaQueryResponse = session.query(
                    yql=f"select created_utc,subreddit_name from reddit_post where subreddit_name contains '{subreddit}' order by created_utc desc",
                    hits=10,
                    summary='minimal',
                )
                if len(response.hits) == 0:
                    return None
                print("Latest Subreddit Time:",datetime.fromtimestamp(response.hits[0]['fields']['created_utc']))
                return datetime.fromtimestamp(response.hits[0]['fields']['created_utc'], tz=timezone.utc)
        except Exception as e:
            log.error(f"Error getting latest subreddit post: {e}")
            return None

    def get_earliest_subreddit_time(self, subreddit):
        if not self.app:
            log.error("Vespa client is not initialized.")
            return None

        try:
            with self.app.syncio() as session:
                response: VespaQueryResponse = session.query(
                    yql=f"select created_utc,subreddit_name from reddit_post where subreddit_name contains '{subreddit}' order by created_utc asc",
                    hits=10,
                    summary='minimal',
                )
                if len(response.hits) == 0:
                    return None
                print("Earliest Subreddit Time:",datetime.fromtimestamp(response.hits[0]['fields']['created_utc']))
                return datetime.fromtimestamp(response.hits[0]['fields']['created_utc'], tz=timezone.utc)
        except Exception as e:
            log.error(f"Error getting earliest subreddit post: {e}")
            return None
    
    def search_multi_threaded_multiple_queries(self, queries):
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(self.query, query): query for query in queries}

            for future in as_completed(future_to_query):
                try:
                    combined_results = future.result()
                    for item_id, result in combined_results:
                        if item_id not in results or result['relevance_score'] > results[item_id]['relevance_score']:
                            results[item_id] = result
                except Exception as e:
                    logging.error(f"Error with query: {e}")

        # Convert the dictionary to a list and sort by combined_score in descending order
        sorted_results = sorted(results.values(), key=lambda x: x['relevance_score'], reverse=True)
        return sorted_results
