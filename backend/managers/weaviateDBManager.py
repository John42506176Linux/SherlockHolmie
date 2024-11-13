import weaviate
import os
import logging
from dotenv import load_dotenv
from utilities.utils import embed_documents
from weaviate.classes.query import MetadataQuery, HybridVector, HybridFusion
from weaviate.classes.aggregate import GroupByAggregate
from weaviate.classes.query import Sort, Filter
from weaviate.util import generate_uuid5
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.config import ConnectionConfig
from managers.keywordManager import KeywordManager
from managers.embeddedManager import CustomEmbedder
import time



log = logging.getLogger("WeaviateManager")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv(override=True)

class WeaviateManager:
    def __init__(self):
        self.url = os.getenv("WCS_URL")
        self.api_key = os.getenv("WCS_API_KEY")
        self.client = weaviate.connect_to_weaviate_cloud(
                cluster_url=self.url,
                auth_credentials=weaviate.auth.AuthApiKey(self.api_key),
                additional_config=AdditionalConfig(
                    connection=ConnectionConfig(
                        session_pool_connections=30,
                        session_pool_maxsize=200,
                        session_pool_max_retries=10,
                    ),
                    timeout=Timeout(init=1440, query=1440, insert=1440)  # Values in seconds
                )
            )
        self.keywords_manager = KeywordManager()
        self.embedder = CustomEmbedder(model_name=os.getenv('AWS_EMBEDDING_MODEL'))
        self.reddit_collection = self.client.collections.get("RedditDB")
    
    def close(self):
        log.info("Closing weaviate client")
        self.client.close()

    def bulk_insert_weaviate(self, posts):
        # Assuming posts is a list of dictionaries
        log.info("Embedding posts")
        post_bodies = [f"{post['body']}" for post in posts]
        log.info("Extracting post embeddings")
        start_time = time.time()
        posts_vectors,word_embeddings = self.keywords_manager.custom_kw_model.extract_embeddings(post_bodies,vectorizer=self.keywords_manager.vectorizer)
        log.info(f"Elapsed Time for post embedding: {time.time()-start_time}")
        log.info("Extracting title embeddings")
        start_time = time.time()
        title_vectors = self.embedder.embed([f"{post['title']}" for post in posts])
        log.info(f"Elapsed Time for title embedding: {time.time()-start_time}")
        # posts
        log.info("Getting keywords")
        start_time =  time.time()
        keywords = self.keywords_manager.get_keywords(post_bodies,doc_embeddings=posts_vectors,word_embeddings=word_embeddings)
        log.info(f"Elapsed Time for keyword extraction: {time.time()-start_time}")
        log.info("Embedding keywords")
        start_time = time.time()
        keyword_vectors = self.keywords_manager.embed_keywords()
        log.info(f"Elapsed Time for keyword embedding: {time.time()-start_time}")
        log.info("Inserting into Weaviate")
        
        property_rows = [
            {
                "title": post['title'],
                "body": post['body'],
                "parent_post": post['parent_post'],
                "num_comments": post['num_comments'],
                "author": post['author'],
                "subreddit_name": post['subreddit'],
                "permalink": post['permalink'],
                "created_utc": datetime.fromtimestamp(post['created_utc'], tz=timezone.utc).isoformat(),
                "is_post": post['is_post'],
                "archived": post['archived'],
                "score": post['score'],
                "link_id": post['link_id'],
                "parent_id": post['parent_id'],
                "parent_post": post['parent_post'],
                "reddit_id": post['id'],
                "keywords" : ', '.join([item[0] for item in keyword]),
            } for post,keyword in zip(posts,keywords)
        ]
        start_time = time.time()

        with self.reddit_collection.batch.fixed_size(batch_size=50)as batch:
            for i, data_row in enumerate(property_rows):
                batch.add_object(
                    properties=data_row,
                    vector={
                        "title_vector": title_vectors[i],
                        "posts_vector": posts_vectors[i],
                        "keywords_vector": keyword_vectors[i],
                    },
                    uuid=generate_uuid5(data_row['reddit_id'])
                )
        failed_objs_a = self.reddit_collection.batch.failed_objects
        if failed_objs_a:
            log.info(f"Number of failed objects in the first batch: {len(failed_objs_a)}")
            for i, failed_obj in enumerate(failed_objs_a, 1):
                log.info(f"Failed object {i}:")
                log.info(f"Error message: {failed_obj.message}")
        log.info(f"Num Errors: {batch.number_errors}")
        log.info(f"Elapsed Insertion Time:{time.time()-start_time}")
        log.info("Batch completed")


    def query_weaviate(self,query, query_vector,target_vector, query_properties,alpha=0.7,limit=10,ids=[],distance=0.40):
        if not self.client:
            log.error("Weaviate client is not initialized.")
            return []
        
        results = []
        max_retries = 5
        retry_delay = 10  # seconds
        response = None
        for attempt in range(max_retries):
            try:
                if ids:
                    uuids = [generate_uuid5(id) for id in ids]
                    response = self.reddit_collection.query.hybrid(
                        query=query,
                        vector=HybridVector.near_vector(
                            vector=query_vector,
                            distance=distance,
                        ),
                        filters=Filter.by_id().contains_any(uuids),
                        fusion_type=HybridFusion.RELATIVE_SCORE,
                        target_vector=target_vector,
                        query_properties=query_properties,
                        alpha=alpha,
                        return_metadata=MetadataQuery(score=True, explain_score=True),
                        limit=limit,
                    )
                else:
                    response = self.reddit_collection.query.hybrid(
                        query=query,
                        vector=HybridVector.near_vector(
                            vector=query_vector,
                            distance=distance,
                        ),
                        fusion_type=HybridFusion.RELATIVE_SCORE,
                        target_vector=target_vector,
                        query_properties=query_properties,
                        alpha=alpha,
                        return_metadata=MetadataQuery(score=True, explain_score=True),
                        limit=limit,
                    )
                log.info(f"Success {attempt}")
                break  # If successful, break out of the retry loop
            except Exception as e:
                if attempt < max_retries - 1:
                    log.warning(f"Attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                else:
                    log.error(f"All {max_retries} attempts failed. Last error: {e}")
                    raise  # Re-raise the last exception if all retries fail
        for o in response.objects:
            results.append({
                "id": o.properties["reddit_id"],
                "title": o.properties["title"],
                "body": o.properties["body"],
                "parent_post": o.properties["parent_post"],
                "num_comments": o.properties["num_comments"],
                "author": o.properties["author"],
                "subreddit_name": o.properties["subreddit_name"],
                "permalink": o.properties["permalink"],
                "created_utc": o.properties["created_utc"],
                "is_post": o.properties["is_post"],
                "archived": o.properties["archived"],
                "score": o.properties["score"],
                "link_id": o.properties["link_id"],
                "parent_id": o.properties["parent_id"],
                "reddit_id": o.properties["reddit_id"],
                "keywords": o.properties["keywords"],
                "relevance_score": o.metadata.score,
            })
        return results

    def get_subreddits(self):
        if not self.client:
            log.error("Weaviate client is not initialized.")
            return []

        try:
            response =  self.reddit_collection.aggregate.over_all(
                group_by=GroupByAggregate(prop="subreddit_name")
            )
            log.info(f"Test:{response}")

            for group in response.groups:
                print(f"Value: {group.grouped_by.value} Count: {group.total_count}")
        except Exception as e:
            log.error(f"Error getting subreddits: {e}")

    def get_latest_subreddit_time(self, subreddit):
        if not self.client:
            log.error("Weaviate client is not initialized.")
            return None

        try:
            response =  self.reddit_collection.query.fetch_objects(
                filters=Filter.by_property("subreddit_name").equal(subreddit),
                sort=Sort.by_property(name="created_utc", ascending=False),
                limit=1
            )
            if response.objects:
                return response.objects[0].properties['created_utc']
            return None
        except Exception as e:
            log.error(f"Error getting latest subreddit post: {e}")
            return None

    def get_earliest_subreddit_time(self, subreddit):
        if not self.client:
            log.error("Weaviate client is not initialized.")
            return None

        try:
            response =  self.reddit_collection.query.fetch_objects(
                filters=Filter.by_property("subreddit_name").equal(subreddit),
                sort=Sort.by_property(name="created_utc", ascending=True),
                limit=1
            )
            if response.objects:
                return response.objects[0].properties['created_utc']
            return None
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