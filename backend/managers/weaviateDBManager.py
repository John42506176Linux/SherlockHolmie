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


log = logging.getLogger("WeaviateManager")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()

class WeaviateManager:
    def __init__(self):
        self.url = os.getenv("WCS_URL")
        self.api_key = os.getenv("WCS_API_KEY")
        self.client = self.connect_to_weaviate()

    def connect_to_weaviate(self):
        try:
            client = weaviate.connect_to_wcs(
                cluster_url=self.url,
                auth_credentials=weaviate.auth.AuthApiKey(self.api_key)
            )
            return client
        except Exception as e:
            log.error(f"Failed to connect to Weaviate: {e}")
            return None
    
    def close(self):
        self.client.close()

    def query_weaviate(self,query, query_vector,target_vector, query_properties,alpha=0.7,limit=10,ids=[],distance=0.40):
        if not self.client:
            log.error("Weaviate client is not initialized.")
            return []
        
        results = []
        try:
            collection = self.client.collections.get("RedditDB")
            reponse = None
            if ids:
                uuids = [generate_uuid5(id) for id in ids]
                response = collection.query.hybrid(
                    
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
                response = collection.query.hybrid(
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
        except Exception as e:
            log.error(f"Error querying Weaviate: {e}")

        return results

    def get_subreddits(self):
        if not self.client:
            log.error("Weaviate client is not initialized.")
            return []

        try:
            collection = self.client.collections.get("RedditDB")
            response = collection.aggregate.over_all(
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
            collection = self.client.collections.get("RedditDB")
            response = collection.query.fetch_objects(
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
            collection = self.client.collections.get("RedditDB")
            response = collection.query.fetch_objects(
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
    
    def search_multiple_queries(self, queries):
        results = {}
        with ThreadPoolExecutor() as executor:
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

        combined_results = []

        # Combine results only if they appear in all three sources
        for obj in post_results:
            post_id = obj['id']
            if post_id in keyword_dict and post_id in title_dict:
                combined_result = {
                    "parent_post": obj['parent_post'],
                    "num_comments": obj['num_comments'],
                    "author": obj['author'],
                    "subreddit_name": obj['subreddit'],
                    "created_utc": datetime.fromtimestamp(obj['created_utc'], tz=timezone.utc).isoformat(),
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
                combined_results.append(combined_result)

        # Sort the combined results by the combined score and return the top 20
        sorted_results = sorted(combined_results, key=lambda x: x['relevance_score'], reverse=True)

        return sorted_results