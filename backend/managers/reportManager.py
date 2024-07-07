from managers.databaseManager import DatabaseManager
from langchain.docstore.document import Document
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    HarmBlockThreshold,
    HarmCategory,
)
from langchain_community.document_transformers import (
    LongContextReorder,
)
from langchain.docstore.document import Document
from langchain_aws import ChatBedrock
from langchain_community.chat_models import ChatOpenAI
from constants import  reddit_constants
from models.llm_models import PainPointsModel,ClusterAnalysis,ValidCluster,InvalidCluster,PainPointCluster,PainPointClusterItem,PersonaResponse,ValidPersonaCluster,InvalidPersonaCluster,PersonaCluster,PersonaClusterItem,ClusterPersonaAnalysis
from prompts import gemini_prompts,openai_prompts
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from typing import Any
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from utilities.utils import EMOTION_VALUES,extract_post_title_from_permalink
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser,JsonOutputParser
from collections import defaultdict
import logging.handlers
from collections import Counter
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.llms.bedrock import Bedrock
from parsers.error_json_parser import ErrorJsonParser
import cohere
from typing import List,Dict
import time
from InstructorEmbedding import INSTRUCTOR
from tqdm import tqdm
import json
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AffinityPropagation
from sklearn.metrics.pairwise import euclidean_distances
from managers.test import FILTERED_RERANKED_TEST_DATA

# TODO: Set up full logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

class BatchCallback(BaseCallbackHandler):
	def __init__(self, total: int):
		super().__init__()
		self.count = 0
		self.progress_bar = tqdm(total=total) # define a progress bar

	# Override on_llm_end method. This is called after every response from LLM
	def on_llm_end(self, response, *, run_id: UUID, parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
		self.count += 1
		self.progress_bar.update(1) # update the progress bar
          
class ReportManager:
    def __init__(self,db_manager:DatabaseManager):
        self.db_manager = db_manager
        self.report_type = "Space" # TODO: Turn this into a class attribute
        self.large_json_llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest",safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_VIOLENCE: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_NONE,
        },).bind(generation_config={ "response_mime_type": "application/json"}).with_retry(
            # retry_if_exception_type=(ValueError,), # Retry only on ValueError
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        ) # TODO: Create an LLM class
        self.fast_llm = ChatBedrock(
            model_id="anthropic.claude-3-sonnet-20240229-v1:0",
            model_kwargs={"temperature": 0},
        ).with_retry(
            # retry_if_exception_type=(ValueError,), # TODO: Figure out with errors to retry on
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
        self.flash_gemini_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_VIOLENCE: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_NONE,
        },).with_retry(
            # retry_if_exception_type=(ValueError,), # Retry only on ValueError
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
        self.openai_small_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo").with_retry(
            # retry_if_exception_type=(ValueError,), # Retry only on ValueError
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
        self.openai_big_llm =  ChatOpenAI(temperature=0, model="gpt-4o",max_retries=30).bind(response_format={ "type": "json_object" }).with_retry(
            # retry_if_exception_type=(ValueError,), # Retry only on ValueError
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
        self.openai_small_llm_json = ChatOpenAI(temperature=0, model="gpt-3.5-turbo").with_retry(
            # retry_if_exception_type=(ValueError,), # Retry only on ValueError
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
        self.bedrock_small_qa_chain = load_qa_with_sources_chain(self.fast_llm, chain_type="stuff")
        self.gemini_pro_json_qa_chain = load_qa_with_sources_chain(self.large_json_llm, chain_type="stuff")
        self.gemini_flash_qa_chain = load_qa_with_sources_chain(self.flash_gemini_llm, chain_type="stuff")
        self.openai_small_chain = load_qa_with_sources_chain(self.openai_small_llm_json, chain_type="stuff")
        self.openai_big_chain = load_qa_with_sources_chain(self.openai_big_llm, chain_type="stuff")
        self.cohere_client = cohere.Client()
        self.space_info = None
        self.space = None
        self.top_documents = None
        self.top_texts = None
        self.pain_points = None
        self.personas = None
        self.author_texts = None
        self.query_info =  None
        self.query = None
        self.top_query_documents = None
        self.insights = None
        self.perspective = None
        self.context = None
        self.gemini_prompts = gemini_prompts.GeminiPrompts()
        self.openai_prompts = openai_prompts.OpenAIPrompts()
        self.max_retries = 5
        self.reranked_rows_dict = {}
        self.embedding_model = INSTRUCTOR('hkunlp/instructor-large')

    def _get_emotion_value(self,emotion,emotion_values):
        try:
            if isinstance(emotion, dict) and "enum" in emotion:
                emotion = emotion["enum"][0] 
            if isinstance(emotion,str):
                emotion = emotion_values.get(emotion, 0)
            return emotion
        except Exception as e:
            log.error(f"Error getting emotion value: {e}")
            return 0
    def _process_pain_points(self,results, emotion_values):
        filtered_pain_points = []
        log.info("Processing Pain Points")
        for result in results:
            if result:
                pain_points = result.get('pain_points', [])
                if pain_points:
                    for pain_point in pain_points:
                        try:
                            issue_topic = pain_point.get('issue_topic', {})
                            post_id = pain_point.get('post_id', '')
                            # Check if issue_topic is a string (LLM bug case)
                            if isinstance(issue_topic, str):
                                continue  # Skip this pain point if issue_topic is a string
                            issue_emotion = pain_point.get('issue_emotion', '')
                            emotion_value = self._get_emotion_value(issue_emotion,emotion_values)
                            if emotion_value < -0.4 and issue_topic.get('match_space_topic', False) and issue_topic.get('match_quote_pain',True) and pain_point.get('is_quote_relevant', False) and post_id in self.reranked_rows_dict:
                                filtered_pain_points.append(pain_point)
                        except Exception as e:
                            log.info(f"Pain Point:{pain_point}")
                            log.error(f"Error processing pain points: {e}")
        return filtered_pain_points

    def initialize_query(self,query,perspective,space,context,fast=True,threshold=0.55):
        if self.query_info is not None:
            log.error("Query already initialized")
            return None
        query_str = f"Write an authentic post about the {space} space from {perspective} perspective helping answer the following query {query}"
        hyde = HyDEQueryTransform(include_original=True)
        hyde.llm = Bedrock( model="anthropic.claude-3-haiku-20240307-v1:0",aws_region_name="us-east-1")
        query_bundle = hyde(query_str)
        query_info = self.db_manager.space_search_query(query_bundle.embedding_strs[0],fast,threshold)
        self.query_info = self.batch_rerank(query_info,space)[:5000]
        self.perspective = perspective
        self.context = context
        self.query = query
        docs = [
                Document(
                    page_content=row['body'],
                    metadata={
                        "source": {
                            'Author': row['author'],
                            'Link': reddit_constants.REDDIT_URL + row['permalink'],
                            'Time': row['created_utc']
                        }
                    }
                ) 
                for row in self.query_info
            ]
        reordering = LongContextReorder()
        self.top_query_documents = reordering.transform_documents(docs)
        self.top_query_texts = [row['body'] for row in self.query_info]
        aggregated_data = {}
        # Iterate through the list and aggregate the text
        for row in self.query_info:
            author = row['author']
            body = row['body']
            
            if author  in aggregated_data:
                aggregated_data[author]['Text'] += 'Post: ' + body + ' \n '
                aggregated_data[author]['Num_Posts'] += 1
                
            else:
                aggregated_data[author] = {}
                aggregated_data[author]['Num_Posts'] = 1
                aggregated_data[author]['Text']  = 'Post: ' + body + ' \n '
        self.top_query_texts = [data['Text'] for data in aggregated_data.values()]
        if self.space is None:
            self.space = space

    def _batch_insights(self,batch_size=50,concurrency=5):
        input_dicts = []

        prompt =  self.gemini_prompts.get_prompt(name="batch_insight_prompt",refined_query=self.query,user_segment=self.perspective,context=self.context)
        for i in range(0, len(self.top_query_documents), batch_size):
            batch = self.top_query_documents[i : i + batch_size]
            input_dict = {"question": prompt, "input_documents": batch}
            input_dicts.append(input_dict)
        full_insights = []
        insights = self.gemini_flash_qa_chain.batch(input_dicts, config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(input_dicts))]})
        for insights_str in insights:
            full_insights.append(insights_str['output_text'])
        return full_insights
    
    def _summarize_insights(self,insights):
        prompt = self.openai_prompts.get_prompt(name="summarize_insights_json_prompt",refined_query=self.query,space=self.space,user_segment=self.perspective,context=self.context)
        full_insights = ""
        for insight in insights:
            full_insights += insight + '\n'
        template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            ("human", "{query}")
        ])
        chain = template | self.openai_big_llm | StrOutputParser()

        # Chain Invoke
        response = chain.invoke({"query": full_insights})
        return response

    def initialize_space(self,space,perspective,context,fast=True,threshold=0.55):
        if self.space_info is not None:
            log.error("Space already initialized")
            return None
        query_str = f"Write an authentic post about the {space} space from {perspective} perspective discussing potential pain points"
        hyde = HyDEQueryTransform(include_original=True)
        query_bundle = hyde(query_str)
        hyde_doc = query_bundle.embedding_strs[0]
        space_info = self.db_manager.space_search_query(hyde_doc,fast,threshold)
        self.space_info = self.batch_rerank(space_info,space)[:5000]
        self.reranked_rows_dict =  {d['id']: {k: v for k, v in d.items() if k != 'id'} for d in self.space_info}
        self.space = space
        docs = [
                Document(
                    page_content=row['body'],
                    metadata={
                        "source": {
                            'Author': row['author'],
                            'Link': reddit_constants.REDDIT_URL + row['permalink'],
                            'Time': row['created_utc']
                        }
                    }
                ) 
                for row in self.space_info
            ]
        reordering = LongContextReorder()
        self.top_documents = reordering.transform_documents(docs)
        self.top_texts = [row['body'] for row in self.space_info]
        # Assuming self.space_info is a list of dictionaries with 'author', 'body', and 'similarity' keys
        aggregated_data = defaultdict(lambda: {'Num_Posts': 0, 'Posts': []})

        # Aggregate data
        for row in self.space_info:
            author = row['author']
            body = row['body']
            similarity = row['relevance_score']
            aggregated_data[author]['Posts'].append({'body': body, 'similarity': similarity})
            aggregated_data[author]['Num_Posts'] += 1

        # Select top 20 texts for each author based on similarity
        for author, data in aggregated_data.items():
            top_posts = sorted(data['Posts'], key=lambda x: x['similarity'], reverse=True)[:10]
            aggregated_data[author]['Text'] = ' \n '.join('Post: ' + post['body'] for post in top_posts)

        self.perspective = perspective
        self.context = context
        self.author_texts = [data['Text'] for data in aggregated_data.values()]
    
    def batch_rerank(self,rows, query, batch_size=1000,threshold=0.65):
        all_reranked = []
        
        for i in tqdm(range(0, len(rows), batch_size)):
            batch = rows[i:i+batch_size]
            texts = [row["combined_text"] for row in batch]
            try:
                results = self.cohere_client.rerank(
                    query=query,
                    documents=texts,
                    top_n=len(texts),  # Rerank all in the batch
                    model='rerank-english-v2.0'
                )
                for result in results.results:
                    original_row = batch[result.index]
                    all_reranked.append({
                        **original_row,
                        "relevance_score": result.relevance_score
                    })
            except Exception as e:
                log.error(f"Error reranking:{e}")
            time.sleep(5)
        all_reranked = sorted(all_reranked, key=lambda x: x["relevance_score"], reverse=True)
        filtered_reranked_space_rows = [row for row in all_reranked if row['relevance_score'] > threshold]
        return filtered_reranked_space_rows
    
    def get_space_size(self):
        return len(self.space_info)

    def get_query_size(self):
        return len(self.query_info)

    def _batch_pain_points(self,batch_size=50,concurrency=5):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=PainPointsModel))
        persona_titles = []
        if self.personas:
            persona_titles = [f"{persona_cluster.title} Description: {persona_cluster.description}" 
                  for persona_cluster in self.personas[:-1]]
        system_template = """You are an entrepreneur researching the pain points consumers of a certain perspective have inside a given space. You'll be provided with various Reddit posts related to this space some relevant, some not.

        Your Goal: Extract a comprehensive list of clear, specific pain points mentioned directly in these posts. Follow these steps carefully:

        If the user mentioned a specific product/process/service in the perspective.
        - Find pain points that are specifically about this product/process/service

        - A relevant topic is defined by one that highly related and helps meet the business objective.

        1. Read each Reddit post/comment thoroughly.
        2. Identify pain points that are clearly and directly mentioned in the perspective given.
        2a. To find a pain point find posts where relevant topics are being discussed negatively.
        2b. Find the particular issue with the topic being discussed. You can create multiple pain points for a singular post for longer posts.
        2c. Identify the user perspective that this post is coming from. To identify the perspective this post is coming from review the post to see what the user has mentioned, and you may make some general inference based on the subreddit, but inferences made on the subreddit should have lower confidence scores.If you've only inferred an attribute based off of subreddit use a confidence score of 0.3. Compare against the given perspective and it's weights to determine a perspective match score based on the confidence,similarity, and weight.
        3. Avoid extrapolating or inferring pain points not explicitly stated.
        4. If no pain point is found, it is acceptable to have empty outputs. No Pain Points is better than inferior ones.
        6. Keep the context/business objective in mind/ but do not let it bias your extraction.
        7. For each pain point, classify it under the given personas, enter null if it is unclear.

        Key Instructions:

        - DO NOT HALLUCINATE QUOTES OR LINKS: If unsure, do not include the pain point. Only include high-quality, directly mentioned pain points.
        - VISIBLE QUOTES AND LINKS: Ensure the quote or link is fully visible if a pain point is included.
        - NO EXTRAPOLATION: Only choose pain points explicitly mentioned by the user.

        Requirements:

        - Quality: Each pain point must be:
        - Relevant: The quote must directly and unambiguously reflect the pain point.
        - Specific: Avoid vague or general issues unspecific to the specific, like "Negative Experiences". Focus on what is specifically causing the pain for this space in the given quote.
        - Directional: Use action-oriented language to convey the nature of the problem (e.g., "Difficulty in...", "Lack of...").
        - Readable: Write in clear, concise language, avoiding jargon and overly technical terms.
        - Accurate: Faithfully represent the pain points expressed in the Reddit posts.

        Reddit-Specific Exclusions:

        - DO NOT INCLUDE pain points that are exclusively relevant to Reddit's platform or user experience (e.g., issues with subreddits, karma, or site features).

        Evaluation Criteria:

        - Relevance is the top priority. If a quote does not strongly and unambiguously support the pain point, it should not be included.
        - Specificity is the next highest priority the more specific a pain point is the more valuable and actionable it will be to users.
        - Directionality, readability, and accuracy are all important factors in determining how a pain point should be represented.
        - Quote quality - The quote should clearly demonstrate the pain point. If not, it should not be included.

        {format_instructions}
        """

        user_template = """
        Personas:{personas}
        Space: {space}
        Perspective: {perspective}
        Business Objective: {context}
        {posts}
        """

        chat_template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", user_template),
        ])
        queries = []
        log.info(f'Batch Size:{batch_size}')
        for i in range(0, len(self.space_info), batch_size):
            batch = self.space_info[i : i + batch_size]
            posts_str = ""
            for post in batch:
                posts_str += f"""
                - POST:
                - Text: {post['body']}
                - Link: https://www.reddit.com{post['permalink']}
                - Created At: {post['created_utc']}
                - Author: {post['author']}
                - Score: {post['score']}
                - Archived: {post['archived']}
                """

            queries.append({
                "space" : self.space,
                "perspective" : self.perspective,
                "context" : self.context,
                "personas" : persona_titles,
                "posts" : posts_str,
                "format_instructions" : parser.get_format_instructions()
            })
        
        chain = chat_template | self.openai_big_llm | parser
        log.info("Starting Batch Pain Points")
        # Chain Invoke
        response = chain.batch(queries,config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(queries))]})
        log.info(f'Response Size:{len(response)}')
        log.info("Finished Batch Pain Points")
        return self._process_pain_points(response,EMOTION_VALUES)
    
    def _filter_embeddings(self,relevant_dict, threshold, similarities):
        response_dict = {
            'title': [],
            'description': [],
            'id': [],
            'quote': []
        }
        filtered_similarities = []
        
        for i, (title, description, post_id, quote, similarity) in enumerate(zip(relevant_dict['title'], relevant_dict['description'], relevant_dict['id'], relevant_dict['quote'], similarities)):
            if similarity > threshold:
                response_dict['title'].append(title)
                response_dict['description'].append(description)
                response_dict['id'].append(post_id)
                response_dict['quote'].append(quote)
                filtered_similarities.append(similarity)
        
        return response_dict, filtered_similarities

    def _filter_pain_points(self,processed_pain_points):
        relevant_dict = self._extract_pain_points_info(processed_pain_points)

        log.info(f'Filtering Pain Points:{len(relevant_dict)}')
        instruction = 'Represent the Space Title for Retrieval'
        space_embeddings = self.embedding_model.encode([[instruction,f'{self.space}']])
        pain_point_title_instruction = 'Represent the Pain Point for Retrieval'
        pain_point_title_pairs = []
        for title, description in zip(relevant_dict['title'], relevant_dict['description']):
            pain_point_title_pairs.append([pain_point_title_instruction, f"Title: {title} Description: {description}"])

        # Calculate title embeddings and similarities
        pain_point_title_embeddings = self.embedding_model.encode(pain_point_title_pairs)
        log.info(f'Similarities for Title:{len(pain_point_title_embeddings)}')
        title_similarities = cosine_similarity(space_embeddings, pain_point_title_embeddings)[0]

        # First filter based on title similarities with a 0.80 threshold
        filtered_dict, filtered_similarities = self._filter_embeddings(relevant_dict, 0.6, title_similarities)
        log.info(f'Filtered Title Pain Points:{len(filtered_dict)}')
        # Now apply the second filter
        pain_point_instruction = 'Represent the Space Pain Point for Retrieval'
        pain_point_pairs_filtered = []

        for title, description, post_id in zip(filtered_dict['title'], filtered_dict['description'], filtered_dict['id']):
            try:
                pain_point_instruction = 'Represent the Space Pain Point for Retrieval'
                pain_point_pairs_filtered.append([pain_point_instruction, f"Pain Point Title:{title} Post Title:{extract_post_title_from_permalink(self.reranked_rows_dict[post_id]['permalink'])} {self.reranked_rows_dict[post_id]['combined_text']}"])
            except Exception as e:
                log.error(f"Error filtering pain points:{e}")

        # Calculate pain point embeddings and similarities for the filtered results
        pain_point_embeddings_filtered = self.embedding_model.encode(pain_point_pairs_filtered)
        log.info(f'Similarities for quote:{len(pain_point_embeddings_filtered)}')
        pain_point_similarities = cosine_similarity(space_embeddings, pain_point_embeddings_filtered)[0]

        # Further filter based on pain point similarities with a 0.825 threshold
        final_filtered_dict, final_filtered_similarities = self._filter_embeddings(filtered_dict, 0.0, pain_point_similarities)

        log.info(f'Filtered quote Pain Points:{len(final_filtered_dict)}')

        final_pain_point_instruction = f'Represent the {self.space} Pain Point Title for Retrieval'
        final_pain_point_pairs = []
        for issue in final_filtered_dict['title']:
            final_pain_point_pairs.append([final_pain_point_instruction,f'{issue}'])
        final_pain_point_embeddings = self.embedding_model.encode(final_pain_point_pairs)

        return final_filtered_dict, final_filtered_similarities, final_pain_point_embeddings
    
    def _cluster_pain_points(self,final_filtered_dict, final_filtered_similarities, final_pain_point_embeddings):
        threshold = 0.41
        affinity_model = AffinityPropagation(affinity='euclidean')
        affprop = affinity_model.fit(final_pain_point_embeddings)
        labels = affprop.labels_
        cluster_centers_indices = affprop.cluster_centers_indices_
        cluster_centers = final_pain_point_embeddings[cluster_centers_indices]


        topic_dict = [
            {
                "title": title,
                "id": id_,
                "description": description,
                "link": 'https://www.reddit.com' + self.reranked_rows_dict[id_]['permalink'],
                "score": self.reranked_rows_dict[id_]['score'],
                "quote": quote,
                "time": self.reranked_rows_dict[id_]['created_utc'].strftime('%Y-%m-%dT%H:%M:%SZ')
            }
            for title, description,id_, quote in zip(
                final_filtered_dict['title'],
                final_filtered_dict['description'],
                final_filtered_dict['id'],
                final_filtered_dict['quote']
            )
        ]

            
        # Initialize distances to centers dictionary
        distances_to_centers = {i: [] for i in range(len(cluster_centers))}

        # Calculate distances to cluster centers
        for idx, label in enumerate(labels):
            point = final_pain_point_embeddings[idx].reshape(1, -1)
            center = cluster_centers[label].reshape(1, -1)
            distance = euclidean_distances(point, center)[0][0]
            distances_to_centers[label].append((distance, idx))

        # Filter out items with distance greater than the threshold
        filtered_distances_to_centers = {i: [] for i in range(len(cluster_centers))}
        miscellaneous_cluster = []

        for cluster, distances in distances_to_centers.items():
            for distance, idx in distances:
                if distance <= threshold:
                    filtered_distances_to_centers[cluster].append((distance, idx))
                else:
                    miscellaneous_cluster.append((distance, idx))

        # Move items from clusters with only one item to the miscellaneous cluster
        for cluster, distances in list(filtered_distances_to_centers.items()):
            if len(distances) <= 1:
                miscellaneous_cluster.extend(distances)
                del filtered_distances_to_centers[cluster]
        
        return filtered_distances_to_centers, miscellaneous_cluster, topic_dict
    

    def _cluster_personas(self,final_filtered_dict, final_filtered_similarities, final_persona_embeddings):
        threshold = 0.6

        affinity_model = AffinityPropagation(affinity='euclidean')
        affprop = affinity_model.fit(final_persona_embeddings)
        labels = affprop.labels_
        cluster_centers_indices = affprop.cluster_centers_indices_
        cluster_centers = final_persona_embeddings[cluster_centers_indices]

        topic_dict = [
            {
                "title": title,
                "id": id_,
                "description": description,
                "link": 'https://www.reddit.com' + self.reranked_rows_dict[id_]['permalink'],
                "score": self.reranked_rows_dict[id_]['score'],
                "quote": quote,
                "time": self.reranked_rows_dict[id_]['created_utc'].strftime('%Y-%m-%d')
            }
            for title, description,id_, quote in zip(
                final_filtered_dict['title'],
                final_filtered_dict['description'],
                final_filtered_dict['id'],
                final_filtered_dict['quote']
            )
        ]

            
        # Initialize distances to centers dictionary
        distances_to_centers = {i: [] for i in range(len(cluster_centers))}

        # Calculate distances to cluster centers
        for idx, label in enumerate(labels):
            point = final_persona_embeddings[idx].reshape(1, -1)
            center = cluster_centers[label].reshape(1, -1)
            distance = euclidean_distances(point, center)[0][0]
            distances_to_centers[label].append((distance, idx))

        # Filter out items with distance greater than the threshold
        filtered_distances_to_centers = {i: [] for i in range(len(cluster_centers))}
        miscellaneous_cluster = []

        for cluster, distances in distances_to_centers.items():
            for distance, idx in distances:
                if distance <= threshold:
                    filtered_distances_to_centers[cluster].append((distance, idx))
                else:
                    miscellaneous_cluster.append((distance, idx))

        # Move items from clusters with only one item to the miscellaneous cluster
        for cluster, distances in list(filtered_distances_to_centers.items()):
            if len(distances) <= 1:
                miscellaneous_cluster.extend(distances)
                del filtered_distances_to_centers[cluster]
        
        return filtered_distances_to_centers, miscellaneous_cluster, topic_dict
    
    def _represent_personas(self,filtered_distances_to_centers,miscellaneous_cluster,topic_dict,concurrency=3):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=ClusterPersonaAnalysis))

        system_template = """Analyze the following cluster of related items in the context of the given space. Each item represents a persona relevant to the space. Your task is to:

        Evaluate whether the items represent personas relevant to the given space and perspective. Reject clusters that are too generic, vague, or not clearly related to user frustrations. Note: Clusters where all items have the same persona are valid and should not be rejected.
        Determine if there's a unified theme among the items that fits with the given space and perspective. A unified theme can emerge from items discussing the same or similar personas of users.
        If a unified theme exists:
        a) Create a concise, descriptive title for the persona (3-7 words) that identifies the unique  persona in the cluster.
        b) Select a representative quote from the cluster that best illustrates the persona
        c) Write a brief description summarizing the common persona (1-2 sentences).
        If there's no clear unified theme or if the cluster is too generic (but not if all items discuss the same specific persona):
        State that the cluster lacks a cohesive theme or is too generic, and briefly explain why.

        Remember to focus on the core problem or frustration expressed in the cluster. Avoid using specific names or identifiers mentioned in the items. Ensure that the identified persona is specific, actionable, and clearly related to user frustrations in the given space and perspective.
        Space:
        [The space the pain points are relevant to will be inserted here]
        Perspective:
        [The perspective pain points should be relevant to will be inserted here]
        Cluster:
        [List of cluster items will be inserted here]
        Please provide your analysis in one of the following formats:
        For valid, specific personas with a unified theme:
        title: [Persona Title]
        quote: [Representative Quote from Post that shows the persona]
        quoteId: [Representative Quote Id]
        description: [Brief description of the persona]
        For clusters lacking a cohesive theme or too generic (but not for clusters where all items discuss a similar enough persona):
        reason: This cluster [lacks a cohesive theme / is too generic] because [brief explanation].
        {format_instructions}
        """

        user_template = """
        Space: {space}
        Perspective: {perspective}
        Context:{context}
        Cluster: {cluster}
        """

        chat_template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", user_template),
        ])

        queries = []
        cluster_indices = []
        for cluster, distances in filtered_distances_to_centers.items():
            cluster_str = f"Cluster {cluster}:"
            for distance, idx in distances:
                cluster_str += f"""
                - Persona:
                - Title : {topic_dict[idx]['title']}
                - Description: {topic_dict[idx]['description']}
                - Quote: {topic_dict[idx]['quote']}
                - Quote ID:{topic_dict[idx]['id']}
                """
            queries.append({
                "space" : self.space,
                "perspective" : self.perspective,
                "context" : self.context,
                "cluster" : cluster_str,
                "format_instructions" : parser.get_format_instructions()
            })
            cluster_indices.append(cluster)
        chain = chat_template | self.openai_big_llm | parser

        # Chain Invoke
        response = chain.batch(queries,config={"max_concurrency": concurrency})

        return self._create_persona_cluster(topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster)
    
    def _represent_pain_points(self,filtered_distances_to_centers,miscellaneous_cluster,topic_dict,concurrency=3):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=ClusterAnalysis))

        system_template = """Analyze the following cluster of related items in the context of the given space. Each item represents a pain point or issue experienced by users. Your task is to:

        Evaluate whether the items represent specific, concrete pain points relevant to the given space and perspective. Reject clusters that are too generic, vague, or not clearly related to user frustrations. Note: Clusters where all items discuss the same specific issue are valid and should not be rejected.
        Determine if there's a unified theme among the items that fits with the given space and perspective. A unified theme can emerge from items discussing the same specific issue or closely related issues.
        If a unified theme exists:
        a) Create a concise, descriptive title for the pain point (3-7 words) that identifies the unique specific theme in the cluster.
        b) Select a representative quote from the cluster that best illustrates the pain point with a negative sentiment.
        c) Write a brief description summarizing the common issue (1-2 sentences).
        If there's no clear unified theme or if the cluster is too generic (but not if all items discuss the same specific issue):
        State that the cluster lacks a cohesive theme or is too generic, and briefly explain why.

        Remember to focus on the core problem or frustration expressed in the cluster. Avoid using specific names or identifiers mentioned in the items. Ensure that the identified pain point is specific, actionable, and clearly related to user frustrations in the given space and perspective.
        Space:
        [The space the pain points are relevant to will be inserted here]
        Perspective:
        [The perspective pain points should be relevant to will be inserted here]
        Cluster:
        [List of cluster items will be inserted here]
        Please provide your analysis in one of the following formats:
        For valid, specific pain points with a unified theme:
        title: [Pain Point Title]
        quote: [Representative Quote from Post that shows the pain point with a negative sentiment]
        quoteId: [Representative Quote Id]
        description: [Brief description of the pain point]
        For clusters lacking a cohesive theme or too generic (but not for clusters where all items discuss the same specific issue):
        reason: This cluster [lacks a cohesive theme / is too generic] because [brief explanation].
        {format_instructions}
        """

        user_template = """
        Space: {space}
        Perspective: {perspective}
        Context:{context}
        Cluster: {cluster}
        """

        chat_template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", user_template),
        ])
        queries = []
        cluster_indices = []
        for cluster, distances in filtered_distances_to_centers.items():
            cluster_str = f"Cluster {cluster}:"
            for distance, idx in distances:
                cluster_str += f"""
                - Pain Point:
                - Title : {topic_dict[idx]['title']}
                - Description: {topic_dict[idx]['description']}
                - Quote: {topic_dict[idx]['quote']}
                - Quote ID:{topic_dict[idx]['id']}
                """
            queries.append({
                "space" : self.space,
                "perspective" : self.perspective,
                "context" : self.context,
                "cluster" : cluster_str,
                "format_instructions" : parser.get_format_instructions()
            })
            cluster_indices.append(cluster)
        chain = chat_template | self.openai_big_llm  | parser


        # Chain Invoke
        response = chain.batch(queries,config={"max_concurrency": concurrency})

        return self._create_pain_point_cluster(topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster)

    def _create_persona_cluster(self,topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster):
        persona_clusters = []
        total_items = sum(len(distances) for distances in filtered_distances_to_centers.values())
        miscellaneous_cluster_items =  []
        for distance, idx in miscellaneous_cluster:
            miscellaneous_cluster_items.append(PersonaClusterItem(
                title=topic_dict[idx]['title'],
                quote=topic_dict[idx]['quote'],
                description=topic_dict[idx]['description'],
                score=topic_dict[idx]['score'],
                link=topic_dict[idx]['link'],
                time=topic_dict[idx]['time'],
            ))
        for i, cluster in enumerate(cluster_indices):
            cluster_analysis = response[i]
            if 'validCluster' in cluster_analysis and cluster_analysis['validCluster']:
                valid_cluster = cluster_analysis['validCluster']
                sub_personas = []
                distances = filtered_distances_to_centers[cluster]
                cluster_items_count = len(distances)

                for distance, idx in distances:
                    print(f"Cluster Item Title: {topic_dict[idx]['title']}")
                    sub_personas.append(
                        PersonaClusterItem(
                            title=topic_dict[idx]['title'],
                            quote=topic_dict[idx]['quote'],
                            description=topic_dict[idx]['description'],
                            score=topic_dict[idx]['score'],
                            link=topic_dict[idx]['link'],
                            time=topic_dict[idx]['time'],
                        )
                    )

                percentage = (cluster_items_count / total_items) * 100

                persona_clusters.append(
                    PersonaCluster(
                        title=valid_cluster['title'],
                        quote=valid_cluster['quote'],
                        score=self.reranked_rows_dict[valid_cluster['quoteId']]['score'],
                        link='https://www.reddit.com' + self.reranked_rows_dict[valid_cluster['quoteId']]['permalink'],
                        time=self.reranked_rows_dict[valid_cluster['quoteId']]['created_utc'].strftime('%Y-%m-%d'),
                        description=valid_cluster['description'],
                        sub_personas=sub_personas,
                        percentage=percentage  # Adding the percentage of items in this cluster
                    )
                )
            else:
                distances = filtered_distances_to_centers[cluster]
                for distance, idx in distances:
                    miscellaneous_cluster_items.append(
                        PersonaClusterItem(
                            title=topic_dict[idx]['title'],
                            quote=topic_dict[idx]['quote'],
                            description=topic_dict[idx]['description'],
                            score=topic_dict[idx]['score'],
                            link=topic_dict[idx]['link'],
                            time=topic_dict[idx]['time'],
                        )
                    )
        # Calculate the percentage for miscellaneous cluster
        total_items = sum(cluster.percentage for cluster in persona_clusters) + len(miscellaneous_cluster_items)
        misc_percentage = (len(miscellaneous_cluster_items) / total_items) * 100 if total_items > 0 else 0

        # Safely access the first item in miscellaneous_cluster_items
        first_misc_item = next(iter(miscellaneous_cluster_items), None)
        # Sort the clusters by percentage in descending order
        persona_clusters.sort(key=lambda x: x.percentage, reverse=True)
        # Append the miscellaneous cluster
        if first_misc_item:
            persona_clusters.append(
                PersonaCluster(
                    title='Miscellaneous Personas',
                    quote=getattr(first_misc_item, 'quote', ''),
                    score=getattr(first_misc_item, 'score', 0),
                    link=getattr(first_misc_item, 'link', ''),
                    time=getattr(first_misc_item, 'time', ''),
                    description='Miscellaneous Personas',
                    sub_personas=miscellaneous_cluster_items,
                    percentage=misc_percentage
                )
            )
        return persona_clusters

    def _create_pain_point_cluster(self,topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster):
        pain_point_clusters = []
        total_items = sum(len(distances) for distances in filtered_distances_to_centers.values())

        miscellaneous_cluster_items = []
    
        for distance, idx in miscellaneous_cluster:
            miscellaneous_cluster_items.append(PainPointClusterItem(
            title=topic_dict[idx]['title'],
            quote=topic_dict[idx]['quote'],
            description=topic_dict[idx]['description'],
            score=topic_dict[idx]['score'],
            link=topic_dict[idx]['link'],
            time=topic_dict[idx]['time'],
        ))

        for i, cluster in enumerate(cluster_indices):
            cluster_analysis = response[i]
            if 'validCluster' in cluster_analysis and cluster_analysis['validCluster']:
                valid_cluster = cluster_analysis['validCluster']
                sub_pain_points = []
                distances = filtered_distances_to_centers[cluster]
                cluster_items_count = len(distances)
                for distance, idx in distances:
                    sub_pain_points.append(
                        PainPointClusterItem(
                            title=topic_dict[idx]['title'],
                            quote=topic_dict[idx]['quote'],
                            description=topic_dict[idx]['description'],
                            score=topic_dict[idx]['score'],
                            link=topic_dict[idx]['link'],
                            time=topic_dict[idx]['time'],
                        )
                    )

                percentage = (cluster_items_count / total_items) * 100

                pain_point_clusters.append(
                    PainPointCluster(
                        title=valid_cluster['title'],
                        quote=valid_cluster['quote'],
                        score=self.reranked_rows_dict[valid_cluster['quoteId']]['score'],
                        link='https://www.reddit.com' + self.reranked_rows_dict[valid_cluster['quoteId']]['permalink'],
                        time=self.reranked_rows_dict[valid_cluster['quoteId']]['created_utc'].strftime('%Y-%m-%d'),
                        description=valid_cluster['description'],
                        sub_pain_points=sub_pain_points,
                        percentage=percentage  # Adding the percentage of items in this cluster
                    )
                )
            else:
                distances = filtered_distances_to_centers[cluster]
                for distance, idx in distances:
                    miscellaneous_cluster_items.append(
                        PainPointClusterItem(
                            title=topic_dict[idx]['title'],
                            quote=topic_dict[idx]['quote'],
                            description=topic_dict[idx]['description'],
                            score=topic_dict[idx]['score'],
                            link=topic_dict[idx]['link'],
                            time=topic_dict[idx]['time'],
                        )
                    )
        total_items = sum(cluster.percentage for cluster in pain_point_clusters) + len(miscellaneous_cluster_items)
        misc_percentage = (len(miscellaneous_cluster_items) / total_items) * 100 if total_items > 0 else 0

        # Safely access the first item in miscellaneous_cluster_items
        first_misc_item = next(iter(miscellaneous_cluster_items), None)

        # Append the miscellaneous cluster
        if first_misc_item:
            pain_point_clusters.append(
                PainPointCluster(
                    title='Miscellaneous Pain Points',
                    quote=getattr(first_misc_item, 'quote', ''),
                    score=getattr(first_misc_item, 'score', 0),
                    link=getattr(first_misc_item, 'link', ''),
                    time=getattr(first_misc_item, 'time', ''),
                    description='Miscellaneous Pain Points',
                    sub_pain_points=miscellaneous_cluster_items,
                    percentage=misc_percentage
                )
            )

        # Sort the clusters by percentage in descending order
        pain_point_clusters.sort(key=lambda x: x.percentage, reverse=True)

        return pain_point_clusters

    def _extract_pain_points_info(self,pain_points_model):
        extracted_info = {
            "quote": [],
            "topic_name": [],
            "topic_type": [],
            "topic_keywords": [],
            "issue_name": [],
            "issue_type": [],
            "issue_description": [],
            "title":[],
            "description" : [],
            "score" : [],
            "link": [],
            "time": [],
            "id": [],
            "emotion": []
        }

        for pain_point in pain_points_model:
            try:
                extracted_info["quote"].append(pain_point["quote"])
                extracted_info["topic_name"].append(pain_point["issue_topic"]["name"])
                extracted_info["topic_type"].append(pain_point["issue_topic"]["topic_type"])
                extracted_info["issue_name"].append(pain_point["issue"]["name"])
                extracted_info["issue_type"].append(pain_point["issue"]["issue_type"])
                extracted_info["issue_description"].append(pain_point["issue"]["description"])
                extracted_info["description"].append(pain_point["description"])
                extracted_info["title"].append(pain_point['title'])
                extracted_info["id"].append(pain_point['post_id'])
                extracted_info["link"].append(pain_point['link'])
                extracted_info["score"].append(pain_point['score'])
                extracted_info["time"].append(pain_point['time'])
                extracted_info["emotion"].append(pain_point["issue_emotion"])
            except:
                log.error(f"Error extracting pain points info: {pain_point}")
        return extracted_info
    
    def _parse_strings(self,strings):
        result = []
        for s in strings:
            s = s.replace('<Finish>', '').strip()  # Remove <Finish> and strip any extra whitespace
            if s.startswith('[') and s.endswith(']'):
                items = s[1:-1].split(',')  # Remove the brackets and split by comma
                items = ['None' if not item.strip() else item.strip() for item in items]  # Convert empty strings to None
                result.extend(items)  # Add each item to the result list
            else:
                result.append('None' if not s else s)  # Convert empty strings to None and add the individual item to the result list
        return result
    
    def _count_strings(self,strs):
        parsed_strings = self._parse_strings(strs)
        return Counter(parsed_strings)
    
    def _filter_personas(self,processed_personas):
        persona_dict = self._extract_persona_info(processed_personas)

        space_instruction = 'Represent the Space Title for Retrieval'
        space_embeddings = self.embedding_model.encode([[space_instruction,f'{self.space}']])
        perspective_instruction = 'Represent the Occupation Title for Retrieval'
        perspective_embeddings = self.embedding_model.encode([[perspective_instruction,f'{self.perspective}']])

        persona_title_instruction = 'Represent the Persona for Retrieval'
        persona_title_pairs = []
        for title, description in zip(persona_dict['title'], persona_dict['description']):
            persona_title_pairs.append([persona_title_instruction, f"Title: {title} Description: {description}"])

        # Calculate title embeddings and similarities
        persona_title_embeddings = self.embedding_model.encode(persona_title_pairs)
        title_similarities = cosine_similarity(perspective_embeddings, persona_title_embeddings)[0]

        # First filter based on title similarities with a 0.80 threshold
        filtered_dict, filtered_similarities = self._filter_embeddings(persona_dict, 0.80, title_similarities)

        # Now apply the second filter
        persona_instruction = 'Represent the Persona for Retrieval'
        persona_pairs_filtered = []

        for title, description, post_id in zip(filtered_dict['title'], filtered_dict['description'], filtered_dict['id']):
            try:
                persona_pairs_filtered.append([persona_instruction, f"Persona Title:{title} Post Title:{extract_post_title_from_permalink(self.reranked_rows_dict[post_id]['permalink'])} {self.reranked_rows_dict[post_id]['combined_text']}"])
            except Exception as e:
                print("Damn you hallucinations")

        # Calculate pain point embeddings and similarities for the filtered results
        persona_embeddings_filtered = self.embedding_model.encode(persona_pairs_filtered)
        persona_similarities = cosine_similarity(perspective_embeddings, persona_embeddings_filtered)[0]

        # Further filter based on pain point similarities with a 0.825 threshold
        final_filtered_dict, final_filtered_similarities = self._filter_embeddings(filtered_dict, 0.825, persona_similarities)

        final_persona_instruction = f'Represent the {self.space} Persona Title for Retrieval'
        final_persona_pairs = []
        for persona in final_filtered_dict['title']:
            final_persona_pairs.append([final_persona_instruction,f'{persona}'])
        final_persona_embeddings = self.embedding_model.encode(final_persona_pairs)

        return final_filtered_dict, final_filtered_similarities, final_persona_embeddings 
        
    def get_personas(self,concurrency=3,batch_size=3):
        if self.space is None:
            log.error("Space not initialized")
            return None
        if self.personas is not None:
            log.error("Personas already initialized")
            return None
        if self.perspective is None:
            log.error("Perspective not initialized")
            return None
        log.info("Starting persona extraction")
        if self.personas is None:
            processed_personas = self._batch_personas(batch_size,concurrency)
            log.info("Personas extracted")
            final_filtered_dict, final_filtered_similarities, final_persona_embeddings =  self._filter_personas(processed_personas)
            log.info("Personas filtered")
            filtered_distances_to_centers, miscellaneous_cluster, topic_dict = self._cluster_personas(final_filtered_dict, final_filtered_similarities, final_persona_embeddings)
            log.info("Personas clustered")
            self.personas = self._represent_personas(filtered_distances_to_centers,miscellaneous_cluster,topic_dict,concurrency)
            log.info("Personas represented")
        return self.personas
        
    def _batch_personas(self,batch_size=3,concurrency=3):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=PersonaResponse))
        all_personas = []  # Collect insights from all batches
        input_dicts = []

        system_template = """Create concise 3-5 personas for users who relate to the following space.
        ONLY choose personas that are the exact  user segment.
        Keep in mind the given context given from your superiors.

        Please make sure each of your personas are HIGHLY relevant to the given business context.
        Do not include information that is not directly related to the business context.

        Think step by step in the persona creation process.

        Every persona should be unique and distinct from the others. Each persona should be based on the user segments and the space. Personas should differ based on the user's needs, goals, behaviors. Personas can differ in terms of demographics, culture, background, religion, etc.

        Persona Creation Guidelines:
        - ** TOP PRIORITY: ** Each persona should be directly derived from the Reddit data , have a highly relevant quote,  and should be relevant to the user segment and space.
        - Each persona should be unique and distinct from the others.
        - Personas should be based on the user segments and the space.
        - Personas should differ based on the user's needs, goals, behaviors.
        - Personas can differ in terms of demographics, culture, background, religion, etc.


        These personas will be evaluated on:
        - Relation to the user segment (Personas should fall within the user segment)
        - Relation to the query (Personas should be relevant to the query)
        - Persona Divergence (The personas should not be semantically different from each other in relation to the query)
        - Persona Diversity (The personas should adequately represent the users who relate to the query)
        - Consumer Relevance (The personas should be relevant to entrepreneurs who want to understand this space)

        Requirements:
        - No quote should be used more than ONCE, and each quote should be relevant to the pain point and persona and should be longer than 20 words.
        - DO NOT EXTRAPOLATE the quotes; they should be directly related to the persona and given perspective or pain point they are describing.
        - If an occupation is give you must be CERTAIN that 

        {format_instructions}
        """

        user_template = """
        Space: {space}
        Perspective: {perspective}
        Business Objective: {context}
        {posts}
        """

        chat_template = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", user_template),
        ])
        queries = []
        for i in range(0, len(self.space_info), batch_size):
            batch = self.space_info[i : i + batch_size]
            posts_str = ""
            for post in batch:
                posts_str += f"""
                - POST:
                - Text: {post['body']}
                - Link: https://www.reddit.com{post['permalink']}
                - Created At: {post['created_utc']}
                - Author: {post['author']}
                - Archived: {post['archived']}
                - post_id: {post['id']}
                """

            queries.append({
                "space" : self.space,
                "perspective" : self.perspective,
                "context" : self.context,
                "posts" : posts_str,
                "format_instructions" : parser.get_format_instructions()
            })

        chain = chat_template | self.openai_big_llm  | parser

        # Chain Invoke
        personas_response = chain.batch(queries,config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(queries))]})

        return self._process_personas(personas_response)
    
    def _extract_persona_info(self,personas_model):
        extracted_info = {
            "quote": [],
            "title":[],
            "description" : [],
            "occupation": [],
            "age": [],
            "location": [],
            "link": [],
            "id": [],
        }
        combined_info = []

        for persona in personas_model:
            extracted_info["quote"].append(persona["quote"])
            extracted_info["description"].append(persona["description"])
            extracted_info["title"].append(persona['title'])
            extracted_info["id"].append(persona['post_id'])
            extracted_info["link"].append(persona['link'])
        
        return extracted_info
    def _process_personas(self,results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered_personas = []
        
        for result in results:
            if result:
                personas = result.get('personas', [])
                if personas:
                    for persona in personas:
                        try:
                            if persona.get('is_quote_relevant', False):
                                filtered_personas.append(persona)
                        except Exception as e:
                            print(f"Persona:{persona}")
                            print(f"Error processing personas: {e}")
        
        return filtered_personas

    def get_pain_points(self,concurrency=3,batch_size=3):
        if self.space_info is None :
            raise Exception("Space not initialized")
        elif batch_size < 1 or batch_size > 200:
            raise Exception("Batch size must be between 1 and 200")
        else:
            log.info("Starting pain point extraction")
            if self.pain_points is None:
                processed_pain_points = self._batch_pain_points(batch_size,concurrency)
                log.info("Pain points extracted")
                final_filtered_dict, final_filtered_similarities, final_pain_point_embeddings =  self._filter_pain_points(processed_pain_points)
                log.info("Pain points filtered")
                filtered_distances_to_centers, miscellaneous_cluster, topic_dict = self._cluster_pain_points(final_filtered_dict, final_filtered_similarities, final_pain_point_embeddings)
                log.info("Pain points clustered")
                self.pain_points = self._represent_pain_points(filtered_distances_to_centers,miscellaneous_cluster,topic_dict)
                log.info("Pain points represented")
            return self.pain_points
    
    def get_insights(self,batch_size=50):
        if self.query_info is None :
            raise Exception("Query not initialized")
        elif batch_size < 1 or batch_size > 200:
            raise Exception("Batch size must be between 1 and 200")
        else:
            log.info("Starting insight extraction")
            if self.pain_points is None:
                insights = self._batch_insights(batch_size)
                log.info("Insights extracted")
                self.insights =  json.loads(self._summarize_insights(insights))
                log.info("Insights summarized")
            return self.insights