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



log = logging.getLogger("WeaviateManager")
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

    

    def query_weaviate(self,query, query_vector,target_vector, query_properties,alpha=0.7,limit=10,ids=[],distance=0.40):
        # if not self.client:
        #     log.error("Weaviate client is not initialized.")
        #     return []
        
        # results = []
        # max_retries = 5
        # retry_delay = 10  # seconds
        # response = None
        # for attempt in range(max_retries):
        #     try:
        #         if ids:
        #             uuids = [generate_uuid5(id) for id in ids]
        #             response = self.reddit_collection.query.hybrid(
        #                 query=query,
        #                 vector=HybridVector.near_vector(
        #                     vector=query_vector,
        #                     distance=distance,
        #                 ),
        #                 filters=Filter.by_id().contains_any(uuids),
        #                 fusion_type=HybridFusion.RELATIVE_SCORE,
        #                 target_vector=target_vector,
        #                 query_properties=query_properties,
        #                 alpha=alpha,
        #                 return_metadata=MetadataQuery(score=True, explain_score=True),
        #                 limit=limit,
        #             )
        #         else:
        #             response = self.reddit_collection.query.hybrid(
        #                 query=query,
        #                 vector=HybridVector.near_vector(
        #                     vector=query_vector,
        #                     distance=distance,
        #                 ),
        #                 fusion_type=HybridFusion.RELATIVE_SCORE,
        #                 target_vector=target_vector,
        #                 query_properties=query_properties,
        #                 alpha=alpha,
        #                 return_metadata=MetadataQuery(score=True, explain_score=True),
        #                 limit=limit,
        #             )
        #         log.info(f"Success {attempt}")
        #         break  # If successful, break out of the retry loop
        #     except Exception as e:
        #         if attempt < max_retries - 1:
        #             log.warning(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
        #             time.sleep(retry_delay)
        #         else:
        #             log.error(f"All {max_retries} attempts failed. Last error: {e}")
        #             raise  # Re-raise the last exception if all retries fail
        # for o in response.objects:
        #     results.append({
        #         "id": o.properties["reddit_id"],
        #         "title": o.properties["title"],
        #         "body": o.properties["body"],
        #         "parent_post": o.properties["parent_post"],
        #         "num_comments": o.properties["num_comments"],
        #         "author": o.properties["author"],
        #         "subreddit_name": o.properties["subreddit_name"],
        #         "permalink": o.properties["permalink"],
        #         "created_utc": o.properties["created_utc"],
        #         "is_post": o.properties["is_post"],
        #         "archived": o.properties["archived"],
        #         "score": o.properties["score"],
        #         "link_id": o.properties["link_id"],
        #         "parent_id": o.properties["parent_id"],
        #         "reddit_id": o.properties["reddit_id"],
        #         "keywords": o.properties["keywords"],
        #         "relevance_score": o.metadata.score,
        #     })
        # return results
        pass

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

    def query_keyword_weaviate(self,query,query_vector,ids=[],limit=20):
        return self.query_weaviate(query, query_vector, target_vector=["keywords_vector"], query_properties=["keywords"],alpha=0.6,limit=limit,ids=ids,distance=0.43)

    def query_post_weaviate(self,query,query_vector,ids=[],limit=20):
        return self.query_weaviate(query, query_vector, target_vector=["posts_vector"], query_properties=["body^3","title^2","subreddit_name"],alpha=0.9,limit=limit,ids=ids,distance=0.50)

    def query_title_weaviate(self,query,query_vector,ids=[],limit=20):
        return self.query_weaviate(query,query_vector,target_vector=["title_vector"],query_properties=["title"],alpha=0.7,limit=limit,ids=ids,distance=0.40)
    
    def search_multi_threaded_multiple_queries(self, queries):
        results = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_query = {executor.submit(self.sequential_combine_results, query): query for query in queries}

            for future in as_completed(future_to_query):
                try:
                    combined_results = future.result()
                    for item_id, result in combined_results:
                        if item_id not in results or result['relevance_score'] > results[item_id]['relevance_score']:
                            results[item_id] = result
                except Exception as e:
                    logging.error(f"Error with query {future_to_query[future]}: {e}")

        # Convert the dictionary to a list and sort by combined_score in descending order
        sorted_results = sorted(results.values(), key=lambda x: x['relevance_score'], reverse=True)
        return sorted_results

    def search_multiple_queries(self, queries):
        results = {}

        for query in queries:
            start_time = time.time()
            log.info(f"Processing query: {query}")
            try:
                combined_results = self.sequential_combine_results(query)
                for item_id, result in combined_results:
                    if item_id not in results or result['relevance_score'] > results[item_id]['relevance_score']:
                        results[item_id] = result
            except Exception as e:
                logging.error(f"Error with query {query}: {e}")
            log.info(f"Elapsed Time for query: {time.time()-start_time}")

        # Convert the dictionary to a list and sort by combined_score in descending order
        sorted_results = sorted(results.values(), key=lambda x: x['relevance_score'], reverse=True)
        return sorted_results
    
    def sequential_combine_results(self, query):
        query_vector = embed_documents(os.getenv('AWS_EMBEDDING_MODEL'), [f'Represent this sentence for searching relevant passages:{query}'])[0]
        post_results = self.query_post_weaviate(query, query_vector, limit=10000)
        post_ids = [post['id'] for post in post_results]
        keyword_results = self.query_keyword_weaviate(query, query_vector, limit=10000, ids=post_ids)
        keyword_ids = [keyword['id'] for keyword in keyword_results]
        title_results = self.query_title_weaviate(query, query_vector, limit=10000, ids=keyword_ids)

        # Convert results to dictionaries for easier lookup
        keyword_dict = {obj['id']: obj for obj in keyword_results}
        title_dict = {obj['id']: obj for obj in title_results}

        # Weights for combining scores
        weight_post = 9
        weight_keyword = 2
        weight_title = 1

        combined_results = {}

        # Combine results only if they appear in all three sources
        for obj in post_results:
            post_id = obj['id']
            if post_id in keyword_dict and post_id in title_dict:
                combined_results[post_id] = {
                    "parent_post": obj['parent_post'],
                    "num_comments": obj['num_comments'],
                    "author": obj['author'],
                    "subreddit_name": obj['subreddit_name'],
                    "created_utc": obj['created_utc'],
                    "is_post": obj['is_post'],
                    "archived": obj['archived'],
                    "score": obj['score'],
                    "link_id": obj['link_id'],
                    "parent_id": obj['parent_id'],
                    "id": obj['id'],
                    "body": obj["body"],
                    "keywords": obj['keywords'],
                    "permalink": obj["permalink"],
                    "relevance_score": (
                        weight_post * obj["relevance_score"] +
                        weight_keyword * keyword_dict[post_id]["relevance_score"] +
                        weight_title * title_dict[post_id]["relevance_score"]
                    ) / (weight_post + weight_keyword + weight_title),
                    "title": obj["title"]
                }

        # Sort the combined results by the combined score and return the top 20
        sorted_results = sorted(combined_results.items(), key=lambda x: x[1]['relevance_score'], reverse=True)

        return sorted_results