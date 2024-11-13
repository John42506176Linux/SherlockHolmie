
import weaviate
import os
import logging.handlers
from dotenv import load_dotenv
from utilities.utils import embed_documents
from weaviate.classes.query import MetadataQuery
from weaviate.classes.query import HybridVector,HybridFusion
from weaviate.classes.aggregate import GroupByAggregate
from weaviate.classes.query import Sort,Filter
from weaviate.classes.query import Filter, MetadataQuery # Import classes as needed
from weaviate.util import generate_uuid5
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.config import ConnectionConfig
from managers.weaviateDBManager import WeaviateManager
import time
from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from models.llm_models import *
from langchain_community.chat_models import ChatOpenAI


log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv(override=True)
# Set these environment variables
URL = os.getenv("WCS_URL")
print(f"URL:{URL}")
APIKEY = os.getenv("WCS_API_KEY")
print("API KEY:",APIKEY)
wv_manager = WeaviateManager()


# Connect to a WCS instance
# def query_weaviate(query, query_vector,target_vector, query_properties,alpha=0.7,limit=10,ids=[],distance=0.40):
    

#     results = []
#     start_time = time.time()
#     try:
        
#         reponse = None
#         if ids:
#             uuids = [generate_uuid5(id) for id in ids]
#             response = collection.query.hybrid(
                
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
#             response = collection.query.hybrid(
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
#         print(f"Elapsed Time:{time.time()-start_time}")
#         for o in response.objects:
#             results.append({
#                 "id": o.properties["reddit_id"],
#                 "body": o.properties["body"],
#                 "permalink": o.properties["permalink"],
#                 "title" : o.properties["title"],
#                 "keywords": o.properties["keywords"],
#                 "score": o.metadata.score,
#                 "explain_score": o.metadata.explain_score,
#             })
#     except Exception as e:
#         log.error(f"Error querying Weaviate: {e}")

#     return results

# def get_object_ids(ids):
#     start_time = time.time()
#     client = weaviate.connect_to_wcs(
#         cluster_url=URL,
#         auth_credentials=weaviate.auth.AuthApiKey(APIKEY)
#     )
#     log.info(f"Connection Elapsed Time:{time.time()-start_time}")
#     uuids = [generate_uuid5(id) for id in ids]
#     try:
#         collection = client.collections.get("RedditDB")
#         log.info("Fetch time Start")
#         start_time = time.time()
#         response = collection.query.fetch_objects(
#             filters=Filter.by_id().contains_any(uuids),
#             limit=5
#         )
#         log.info(f"Elapsed Time:{time.time()-start_time}")
#         log.info(f"Test:{response}")
#         return response.objects
#     except Exception as e:
#         log.error(f"Error getting objects:{e}")
#     finally:
#         client.close()
    
# def get_subreddits():
#     client = weaviate.connect_to_wcs(
#         cluster_url=URL,
#         auth_credentials=weaviate.auth.AuthApiKey(APIKEY)
#     )
#     try:
#         collection = client.collections.get("RedditDB")
#         response = collection.aggregate.over_all(
#             group_by=GroupByAggregate(prop="subreddit_name")
#         )
#         log.info(f"Test:{response}")

#         # print rounds names and the count for each
#         for group in response.groups:
#             print(f"Value: {group.grouped_by.value} Count: {group.total_count}")
#     except Exception as e:
#         log.error(f"Error getting subreddits:{e}")
#     finally:
#         client.close()

# def get_latest_subreddit_post(subreddit):
#     client = weaviate.connect_to_wcs(
#         cluster_url=URL,
#         auth_credentials=weaviate.auth.AuthApiKey(APIKEY)
#     )
#     try:
#         collection = client.collections.get("RedditDB")
#         response = collection.query.fetch_objects(
#             filters=Filter.by_property("subreddit_name").equal(subreddit),
#             sort=Sort.by_property(name="created_utc", ascending=False),
#             limit=1
#         )
#         if len(response.objects) > 0:
#             # print rounds names and the count for each
#             return response.objects[0].properties['created_utc']
#         return None
#     except Exception as e:
#         log.error(f"Error getting subreddits:{e}")
#     finally:
#         client.close()


# def get_earliest_subreddit_post(subreddit):
#     client = weaviate.connect_to_wcs(
#         cluster_url=URL,
#         auth_credentials=weaviate.auth.AuthApiKey(APIKEY)
#     )
#     try:
#         collection = client.collections.get("RedditDB")
#         response = collection.query.fetch_objects(
#             filters=Filter.by_property("subreddit_name").equal(subreddit),
#             sort=Sort.by_property(name="created_utc", ascending=True),
#             limit=1
#         )
#         if len(response.objects) > 0:
#             # print rounds names and the count for each
#             return response.objects[0].properties['created_utc']
#         return None
#     except Exception as e:
#         log.error(f"Error getting subreddits:{e}")
#     finally:
#         client.close()


# def query_keyword_weaviate(query,query_vector,ids=[],limit=20):
#     return query_weaviate(query, query_vector, target_vector=["keywords_vector"], query_properties=["keywords"],alpha=0.6,limit=limit,ids=ids,distance=0.43)

# def query_post_weaviate(query,query_vector,ids=[],limit=20):
#     return query_weaviate(query, query_vector, target_vector=["posts_vector"], query_properties=["body^3","title^2","subreddit_name"],alpha=0.9,limit=limit,ids=ids,distance=0.50)

# def query_title_weaviate(query,query_vector,ids=[],limit=20):
#     return query_weaviate(query,query_vector,target_vector=["title_vector"],query_properties=["title"],alpha=0.7,limit=limit,ids=ids,distance=0.60)

# def sequential_combine_results(query):
#     query_vector = embed_documents(os.getenv('AWS_EMBEDDING_MODEL'), [f'Represent this sentence for searching relevant passages:{query}'])[0]
#     post_results = query_post_weaviate(query,query_vector, limit=10000)
#     post_ids = [
#         post['id'] for post in post_results
#     ]
#     keyword_results = query_keyword_weaviate(query,query_vector, limit=10000,ids=post_ids)
#     keyword_ids = [
#         keyword['id'] for keyword in keyword_results
#     ]
#     title_results = query_title_weaviate(query,query_vector, limit=10000,ids=keyword_ids)
#     combined_results = {}

#     # Convert results to dictionaries for easier lookup
#     keyword_dict = {obj['id']: obj for obj in keyword_results}
#     title_dict = {obj['id']: obj for obj in title_results}

#     # Weights for combining scores
#     weight_post = 9
#     weight_keyword = 2
#     weight_title = 1

#     # Combine results only if they appear in all three sources
#     for obj in post_results:
#         post_id = obj['id']
#         if post_id in keyword_dict and post_id in title_dict:
#             combined_results[post_id] = {
#                 "body": obj["body"],
#                 "keywords": obj['keywords'],
#                 "permalink": obj["permalink"],
#                 "post_score": obj["score"],
#                 "keyword_score": keyword_dict[post_id]["score"],
#                 "title_score": title_dict[post_id]["score"],
#                 "combined_score": (
#                     weight_post * obj["score"] +
#                     weight_keyword * keyword_dict[post_id]["score"] +
#                     weight_title * title_dict[post_id]["score"]
#                 ) / (weight_post + weight_keyword + weight_title),
#                 "post_explain_score": obj["explain_score"],
#                 "keyword_explain_score": keyword_dict[post_id].get("explain_score", None),
#                 "title_explain_score": title_dict[post_id].get("explain_score", None),
#                 "title": obj["title"]
#             }

#     # Sort the combined results by the combined score and return the top 20
#     sorted_results = sorted(combined_results.items(), key=lambda x: x[1]['combined_score'], reverse=True)
    
#     return sorted_results

# def combine_results(query):
#     query_vector = embed_documents(os.getenv('AWS_EMBEDDING_MODEL'), [f'{query}'])[0]
#     post_results = query_post_weaviate(query,query_vector, limit=10000)
#     keyword_results = query_keyword_weaviate(query,query_vector, limit=10000)
#     title_results = query_title_weaviate(query,query_vector, limit=10000)

#     combined_results = {}

#     # Convert results to dictionaries for easier lookup
#     keyword_dict = {obj['id']: obj for obj in keyword_results}
#     title_dict = {obj['id']: obj for obj in title_results}

#     # Weights for combining scores
#     weight_post = 9
#     weight_keyword = 2
#     weight_title = 1

#     # Combine results only if they appear in all three sources
#     for obj in post_results:
#         post_id = obj['id']
#         if post_id in keyword_dict and post_id in title_dict:
#             combined_results[post_id] = {
#                 "body": obj["body"],
#                 "keywords": obj['keywords'],
#                 "permalink": obj["permalink"],
#                 "post_score": obj["score"],
#                 "keyword_score": keyword_dict[post_id]["score"],
#                 "title_score": title_dict[post_id]["score"],
#                 "combined_score": (
#                     weight_post * obj["score"] +
#                     weight_keyword * keyword_dict[post_id]["score"] +
#                     weight_title * title_dict[post_id]["score"]
#                 ) / (weight_post + weight_keyword + weight_title),
#                 "post_explain_score": obj["explain_score"],
#                 "keyword_explain_score": keyword_dict[post_id].get("explain_score", None),
#                 "title_explain_score": title_dict[post_id].get("explain_score", None),
#                 "title": obj["title"]
#             }

#     # Sort the combined results by the combined score and return the top 20
#     sorted_results = sorted(combined_results.items(), key=lambda x: x[1]['combined_score'], reverse=True)
    
#     return sorted_results

# log.info(f'Test:{get_earliest_subreddit_post("ChoujinX") + timedelta(seconds=360)}')
# # # Example usage:
hyde_json_parser=JsonOutputParser(pydantic_object=HydeResp)
query  = "How much do bay area residents tend to pay in Home chefs?"
HYDE_PROMPT = PromptTemplate(
        input_variables=["question", "objective"],
        partial_variables={"format_instructions": hyde_json_parser.get_format_instructions()},
        template="""You are an AI language model assistant. Your task is to generate a hypothetical Reddit post based on the given user question. The goal is to create a post that sounds authentic and engaging, which will help in improving the retrieval of relevant documents from a vector database.

        The original question is: {question}
        The business objective is: {objective}
        
        Ensure that the post reflects a conversational tone typically found in Reddit posts, but do not use the word reddit. Feel free to use different ways of expressing the idea or similar terms that might be used in real Reddit discussions.
        Provide the hypothetical Reddit post in valid JSON. ONLY JSON.
        
        {format_instructions}
        """

        )
openai_creative_llm_json =  ChatOpenAI(temperature=0, model="gpt-4o-mini").bind(response_format={ "type": "json_object" }).with_retry(
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
context = "How much are potential customers willing to pay for in home chef services?"
hyde_llm_chain = HYDE_PROMPT | openai_creative_llm_json | hyde_json_parser
hyde_resp = hyde_llm_chain.invoke({
                'question': query,
                'objective': context
            })['hyde']
print(hyde_resp)
combined_sorted = wv_manager.sequential_combine_results(hyde_resp)
# combined_sorted = wv_manager.reddit_collection.query.fetch_objects(limit=20)
# for o in combined_sorted.objects:
#     print(o.properties)
for result_id, result_data in combined_sorted[:20]:
    print(f"ID: {result_id}")
    print(f"Body: {result_data['body']}")
    print(f"Permalink: {result_data['permalink']}")
    print(f"Title: {result_data['title']}")
    # print(f"Post Score: {result_data['post_score']}")
    # print(f"Keyword Score: {result_data['keyword_score']}")
    # print(f"Title Score: {result_data['title_score']}")
    print(f"Combined Score: {result_data['relevance_score']}")
    print(f"Keywords:{result_data['keywords']}")
    # print(f"Post Explain Score: {result_data['post_explain_score']}")
    # print(f"Keyword Explain Score: {result_data['keyword_explain_score']}")
    # print(f"Title Explain Score: {result_data['title_explain_score']}")
    print("-" * 50)  # Separator between results

print(f"Combined Results Len:{len(combined_sorted)}")
wv_manager.close()
# ids = ['ksbsfke','k17aacv']
# get_object_ids(ids)


# get_subreddits()
# keyword_results = query_post_weaviate("Who is the best Choujin?",limit=1000)[:20]
# for obj in keyword_results:
#     print(f"ID: {obj['id']}")
#     print(f"Body: {obj['body']}")
#     print(f"Link: {obj['permalink']}")
#     print(f"Title:{obj['title']}")
#     print(f"Score: {obj['score']}")
#     print(f"Explain Score: {obj['explain_score']}")



    