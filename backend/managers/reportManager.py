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
from models.llm_models import *
from prompts import gemini_prompts,openai_prompts
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from typing import Any
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from utilities.utils import EMOTION_VALUES,extract_post_slug
from langchain_core.prompts.prompt import PromptTemplate
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from collections import defaultdict
import logging.handlers
from collections import Counter
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from parsers.error_json_parser import ErrorJsonParser
from typing import List,Dict
from tqdm import tqdm
import json
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import AffinityPropagation
from sklearn.metrics.pairwise import euclidean_distances
from managers.test import FILTERED_RERANKED_TEST_DATA
from scipy.cluster.hierarchy import linkage, fcluster
from sklearn.preprocessing import normalize
from sklearn.preprocessing import StandardScaler
import requests
import hdbscan
import numpy as np
import os
from langchain_openai import OpenAIEmbeddings
from concurrent.futures import ThreadPoolExecutor, as_completed

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

# TODO: Handle no pain points   
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
        },).bind(generation_config={ "response_mime_type": "application/json"})
        
        self.openai_big_llm = ChatOpenAI(temperature=0, model="gpt-4o-mini").bind(response_format={ "type": "json_object" }).with_retry(
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=30, # Try twice
        )
        self.openai_small_llm_json = ChatOpenAI(temperature=0, model="gpt-4o-mini").with_retry(
            # retry_if_exception_type=(ValueError,), # Retry only on ValueError
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=15, # Try twice
        )
        self.openai_creative_llm_json =  ChatOpenAI(temperature=0, model="gpt-4o-mini").bind(response_format={ "type": "json_object" }).with_retry(
            wait_exponential_jitter=True, # Add jitter to the exponential backoff
            stop_after_attempt=10, # Try twice
        )
        self.sonnet_llm = ChatBedrock(
            model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
            model_kwargs={"temperature": 0},
            region_name="us-east-1"
        )
        self.openai_embedder= OpenAIEmbeddings(model="text-embedding-3-large", dimensions=256, show_progress_bar=True, max_retries=5, retry_max_seconds=120)
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
        self.perspective_specific =False
        self.perspective = None
        self.context = None
        self.gemini_prompts = gemini_prompts.GeminiPrompts()
        self.openai_prompts = openai_prompts.OpenAIPrompts()
        self.max_retries = 5
        self.reranked_rows_dict = {}

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

    def multi_query_generator(self,space,perspective,context):
        query_json_parser=JsonOutputParser(pydantic_object=QueryList)
        hyde_json_parser=JsonOutputParser(pydantic_object=HydeResp)
        QUERY_PROMPT = PromptTemplate(
            input_variables=["space","perspective","objective"],
            partial_variables={"format_instructions": query_json_parser.get_format_instructions()},
            template="""You are an AI language model assistant. 
            Your task is to generate at least 10 different questions to help meet the user's business objective given a space, and the type of perspective they want answers from.
            Your goal is to generate different questions that shows different aspects of the user's question. By generating multiple perspectives/using differing syntaxes on the user question, your goal is to help
            the user overcome some of the limitations of the distance-based similarity search and rerankers.
            Be diverse with the types of question's you ask to cover the full breadth of the user's business objective, but make sure the questions are targeted toward the right perspective and space.
            If the space/or perspective has different names that mean the same thing, include that when generating alternative question.
            You will also be given the business objective the person is trying to solve with this query. Please tailor your questions accordingly.
            Space: {space}
            Perspective:{perspective}
            Objective:{objective}
            Please provide your response in valid JSON. ONLY JSON.
            {format_instructions}
            """,
        )
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
        query_llm_chain = QUERY_PROMPT | self.sonnet_llm | query_json_parser
        hyde_llm_chain = HYDE_PROMPT | self.openai_creative_llm_json | hyde_json_parser
        multiquery_resp = query_llm_chain.invoke(input={
            'space':space,
            'perspective':perspective,
            'objective': context
        })
        hyde_input_list = []
        for resp in multiquery_resp['query']:
            log.info(f"Query:{resp}")
            hyde_input_list.append({
                'question': resp,
                'objective': context
            })
        hyde_resp = hyde_llm_chain.batch(hyde_input_list,config={"max_concurrency": 5,"callbacks": [BatchCallback(len(hyde_input_list))]})
        hyde_queries = [resp['hyde'] for resp in hyde_resp]
        return (hyde_queries,multiquery_resp['query'])

    def initialize_space(self,space,perspective,perspective_specific,context,fast=True,threshold=0.55):
        if self.space_info is not None:
            log.error("Space already initialized")
            return None
        self.space = space
        self.perspective=perspective
        self.context=context
        log.info(f"Space:{self.space} Perspective:{self.perspective} Context:{self.context}")
        hyde_resps,multi_queries = self.multi_query_generator(space,perspective,context)
        space_info  = self.db_manager.search_multiple_queries(multi_queries,hyde_resps, threshold)
        
        log.info(f"Space Info:{len(space_info)}")

        self.space_info = self.full_rerank(space_info, multi_queries, batch_size=512, max_workers=10, perspective_specific=perspective_specific)
        self.reranked_rows_dict =  {d['id']: {k: v for k, v in d.items() if k != 'id'} for d in self.space_info}
       
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
        self.perspective = perspective
        self.context = context
    
    def full_rerank(self,rows, queries, batch_size=512, max_workers=10, perspective_specific=True):
        fast_rows = self.batch_rerank(
            os.getenv('AWS_SMALL_RERANK_MODEL'),
            rows,
            queries,
            threshold=0.001,
            batch_size=batch_size,
            max_workers=max_workers,
            max_posts=float('inf')
        )
        if perspective_specific:
            space_rows = self.batch_rerank(
                os.getenv('AWS_RERANK_MODEL'),
                fast_rows,
                queries,
                threshold=0.15, 
                batch_size=batch_size, 
                max_workers=max_workers, 
                max_posts=float('inf'))[:10000]
            perspective_specific_rows = self.llm_rerank(space_rows)
            return perspective_specific_rows
        else:
            return self.batch_rerank(
                os.getenv('AWS_RERANK_MODEL'),
                fast_rows,
                queries[:5],
                threshold=0.20, 
                batch_size=batch_size, 
                max_workers=max_workers, 
                max_posts=5000)


    def batch_rerank(self,model,rows, queries, threshold=0.50, batch_size=1000, max_workers=10, max_posts=100):
        url = os.getenv('AWS_RERANK_URL')
        log.info(f"Max Posts: {max_posts}")
        log.info(f"Batch Size: {batch_size}")
        all_reranked = defaultdict(lambda: {"max_score": 0, "best_query": None})
        filtered_all_reranked = {}

        def send_request(query, texts):
            payload = {
                "model": model,
                "query": query,
                "documents": texts,
                "return_documents": False,
            }
            try:
                response = requests.post(url, json=payload)
                response.raise_for_status()
                return query, response.json()
            except requests.exceptions.RequestException as e:
                log.error(f"Error reranking for query '{query}': {e}")
                return query, None

        for i in tqdm(range(0, len(rows), batch_size), desc="Processing Batches"):
            batch = rows[i:i+batch_size]
            texts = [f'Subreddit:{row["subreddit_name"]} Title:{extract_post_slug(row["permalink"])} Post: {row["body"]}' for row in batch]
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_query = {executor.submit(send_request, query, texts): query for query in queries}
                for future in as_completed(future_to_query):
                    query = future_to_query[future]
                    try:
                        query, results = future.result()
                        if results:
                            for result in results['results']:
                                original_row = batch[result['index']]
                                doc_id = original_row['id']  # Assuming each row has a unique 'id'
                                score = result['relevance_score']
                                if score > all_reranked[doc_id]["max_score"]:
                                    all_reranked[doc_id] = {
                                        **original_row,
                                        "value": f'Subreddit:{original_row["subreddit_name"]} Title:{extract_post_slug(original_row["permalink"])} Post: {original_row["body"][:2000]}',
                                        "max_score": score,
                                        "best_query": query
                                    }
                    except Exception as e:
                        log.error(f"Error processing query '{query}': {e}")

            # Filter after processing each batch
            filtered_all_reranked = {doc_id: data for doc_id, data in all_reranked.items() if data["max_score"] > threshold}
            log.info(f"Current filtered count: {len(filtered_all_reranked)}")

            if len(filtered_all_reranked) >= max_posts:
                log.info("Max posts limit reached. Stopping processing.")
                break

        # Convert to list and sort by max_score
        reranked_list = list(filtered_all_reranked.values())
        reranked_list.sort(key=lambda x: x["max_score"], reverse=True)

        # Return only up to max_posts
        return reranked_list

    def llm_rerank(self,rows):
        posts = []
        subreddits = []
        llm_reranked_rows = []
        for i, post in enumerate(rows, 1):
            posts.append(post['body'])
            subreddits.append(post['subreddit_name'])

        results = self._analyze_reddit_posts(posts, subreddits)
        log.info("Posts Analyzed")

        for i, (post, analysis_result) in enumerate(zip(rows, results), 1):
            if (analysis_result and 
                analysis_result.get('space_match') is not None and 
                analysis_result.get('perspective_match') is not None and
                analysis_result.get('space_match') and 
                analysis_result.get('perspective_match')):
                # Add the matching post to llm_reranked_rows
                llm_reranked_rows.append(post)
        return llm_reranked_rows

    def _analyze_reddit_posts(self,posts: List[str], subreddits: List[str]):
        # Run the chain
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=RedditPostAnalysis))

        # Define the prompt template
        prompt_template = """
        Your task is to analyze Reddit posts for relevance to a given space and perspective. Here are some examples:

        Example 2:
        Reddit Post: "The James Webb Space Telescope images are mind-blowing! I never thought I'd see such detailed pictures of distant galaxies in my lifetime."
        Space: Space Science
        Perspective: Astronomer
        Subreddit: space
        Analysis:
        {{
        "space_match": true,
        "perspective_match": false
        }}

        Example 3:
        Reddit Post: "As a software engineer, I'm fascinated by the latest developments in quantum computing. The potential for revolutionizing cryptography is huge!"
        Space: Space Science
        Perspective: Software Engineer
        Subreddit: programming
        Analysis:
        {{
        "space_match": false,
        "perspective_match": true
        }}


        Example 4:
        Reddit Post: "IMO as a manager you need to think staff first patients second so that your staff are able to put patients first"
        Space: Nursing Homes in the UK
        Perspective: Nursing Home Manager
        Subreddit: NursingUK
        Analysis:
        {{
        "space_match": false,
        "perspective_match": false
        }}

        Example 5:
        Reddit Post: "From a managers point of view it's difficult. They were supposed to be additional, to 'free up' band 5s for 'more complex tasks' but this hasn't happened. I have to have 1 NA on the ward but that means I have to sacrifice an RN position. 

        So I've had to have one and put them on the rota but they have to run a bay, which means I or the charge nurse that day has to oversee them because technically NA are not supposed to actually 'plan care' just help deliver it, and they're not supposed to do IVs and other things (lots of trusts will be scaling back what they've allowed NA to do in the coming months as they've far surpassed what they were originally for). 

        They're fabulous at what they do but the restrictions to the role are causing problems because the role is being used in the wrong way. Before the role came out lots of us replied to the consultation saying they would be used instead of RN and replace them. We were told we were being silly. Well wel well."
        Space: Nursing Homes in the UK
        Perspective: Nursing Home Manager
        Subreddit: NursingUK
        Analysis:
        {{
        "space_match": false,
        "perspective_match": false
        }}

        Example 6:
        Reddit Post: "Hello,

        Thank you very much for the detailed response. I super appreciate the time you took to write it. 

        I should have clearly stated from the beginning for Buyers to order their own Inspections. 

        I’m in California too. We checked the box for Buyers to pay inspections to make their offer stronger, since there two other offers on the table. 

        I should have clarified with listing agent whether they had inspections available or not prior to writing offer. 

        If the listing agent ordered inspections during the listing period, and the reports happened to be available right after we were in contract, I should have just used those as additional inspections, and not Buyer’s main inspections. Did I understand that right?"

        Space: Real Estate Agents and Inspection Reports
        Perspective: Home Buyer
        Subreddit: realtors
        Analysis:
        {{
        "space_match": false,
        "perspective_match": false
        }}

        Example 7:
        Reddit Post:"Hi all!

        The inspection report for the house I'm under contract for came back and over all it's not looking too bad.

        Safety items found:
        - outside next to the house dip in ground allows pooling of water next to foundation (grading issue)
        - one outside outlet ground fault interruption didn't trigger 
        - tree on front of house has rot in two hollows (otherwise healthy)
        - railing spindles of deck stairs are nailed and not screwed in
        - exposed insulation in the garage
        - garage heater not working (seller disclosed this)
        - exposed wires and outlet not installed in garage (basically outlet is hanging by one wire and a couple other wires are sticking out of the hole in the wall)
        - most outlets in garage not working (inspector assumes that's because of the outlet hanging out of its usual space)
        - handyman lights in the garage
        - two fist size holes in the drywall in the garage of the wall shared with house
        - no second railing on basement stairs (open to the basement/no wall on that side)
        - bathroom door is not opening freely (scratching on floor)
        - spindles of stair railing a can be removed by pushing up and pulling (call me crazy, but I think they are designed to do that?! This way it's easy to replace them, no?)
        - exposed capped wires outside the garage door (wires are for lamp install, but the lamp is not installed)

        Those were the safety items. 
        The repair items are:
        - door stops missing at all interior doors
        - deadbolt of door leading to garage from interior not engaging properly
        - no air gap for sump pump pipes outside
        - third of crawl space is not covered (part full basement, part crawl, the crawl is divided in 2/3 concrete covered, 1/3 dirt (no cover))
        - second sump pump doesn't seem to be operating
        - support columns in basement at not bolted down
        - washer/dryer do not work and need to most likely be replaced
        - shed (size of 1 car garage) needs gutters to prevent rot on the bottom
        - pressure of both showers is low.

        Okay, so overall as you can see not really a bad inspection! 
        I'm in Illinois where it is custom to have it written in the contract that the buyer will only request health/safety things to be fixed and if asking anything more than that the contract can be terminated by the seller. I guess that's for protection of bringing the price down through none sense of the inspection.

        Either way, I will go over the things with my realtor and my lawyer as well, but the things I'm inclined to ask for:

        - grade out the dip at the foundation
        - replace outside outlet that didn't trigger the ground fault interruption
        - fix outlets in the garage 
        - plane the bathroom door

        Now, the repair items I'd like fixed (this is where I need to talk to realtor and lawyer if I can/should request them or if I'm risking the seller to terminate):

        - install bolts for support columns in basement
        - align deadbolt of interior to garage door
        - repair/give allowance for washer and dryer

        Does my list seem reasonable? The washer and dryer are interesting, since they are in the contract as working items, so I would expect I can bring that up as items. Also, if they repair or give me an allowance is that their call or can I just ask for an allowance and they can counter with repair? 

        Thanks all!

        Edit to add: this house is a rebuild, old house (except garage) burned down and the owners rebuilt it. So the inside is basically all brand new, just foundation and garage was reused.
        "
        Space:Inspection Reports for Homes
        Perspective:Home Buyers
        Subreddit:FirstTimeHomeBuyer
        Analysis:
        {{
        "space_match": true,
        "perspective_match": true
        }}

        Now, please analyze the following Reddit post:

        Given the following information:
        Reddit Post: {post}
        Space: {space}
        Perspective: {perspective}
        Subreddit: {subreddit}


        Please analyze the Reddit post and determine:
        1. Is the post topic relevant to the given space? (true/false) 
        - Only state true if the topic the user discusses inside the post is directly relevant to the space.
        2. Is the author of the post from the exact perspective provided? (true/false)
        - Only state true if the user --DIRECTLY OR INDIRECTLY-- states that they are OR was the given perspective. Do not infer based on knowledge expressed. Only state true if you can conclusively prove they are the given perspective.
        4. Explain how the title relates to the space and perspective.

        {format_instructions}

        Analysis:
        """

        # Create a PromptTemplate
        prompt = PromptTemplate(
            input_variables=[ "post", "space", "perspective", "subreddit"],
            template=prompt_template,
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        batch_inputs = []
        for post,subreddit in zip(posts,subreddits):
            batch_inputs.append(
                {
                    "post": post,
                    "space": self.space,
                    "perspective": self.perspective,
                    "subreddit": subreddit
                }
            )
        analyze_chain = prompt | self.openai_small_llm_json | parser
        results = analyze_chain.batch(batch_inputs,config={"max_concurrency": 3,"callbacks": [BatchCallback(len(batch_inputs))]})
    
        return results
    
    def get_space_size(self):
        return len(self.space_info)

    def get_query_size(self):
        return len(self.query_info)

    def _batch_pain_points(self,batch_size=50,concurrency=10):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=PainPointsModel))
        persona_titles = []
        if self.personas:
            persona_titles = [f"{persona_cluster.title} Description: {persona_cluster.description}" 
                  for persona_cluster in self.personas]
        system_template = """You are an entrepreneur researching the pain points consumers of a certain perspective have inside the given space. You'll be provided with various Reddit posts related to this space some relevant, some not.

        Your Goal: Extract a comprehensive list of clear, specific pain points mentioned directly in these posts. Follow these steps carefully:

        1. Read each Reddit post/comment thoroughly.
        2. Identify pain points that are specific to the given space.
        2a. To find a pain point find posts where topics specific to the space are being discussed negatively.
        2b. Find the particular issue with the space being discussed. You can create multiple pain points for a singular post for longer posts.
        4. If no pain point is found, it is acceptable to have empty outputs. No Pain Points is better than inferior ones.
        5. Keep the context/business objective in mind but do not let it bias your extraction.
        6. For each pain point, classify it under the given personas, enter null if it is unclear. Only output the persona title.

        Key Instructions:
        - DO NOT HALLUCINATE QUOTES OR ID: If unsure, do not include the pain point. Only include high-quality, directly mentioned pain points.
        - VISIBLE QUOTES AND POST IS: Ensure the quote or post_id is fully visible if a pain point is included.
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

        Pain Point Title Guidelines:
        - Pain point titles should start with one of the following phrases:
        1. "Lack of..." (for issues related to something missing)
        2. "Difficulty in..." (for issues related to friction or challenges)
        - Ensure the title is specific and clearly communicates the issue and the topic
        - Do not use emotions as part of the pain point title.

        Examples of well-formulated pain points:
        1. Lack of Monitors in Coworking Spaces
        2. Difficulty in Optimizing Video Content for Different Social Media Platforms
        3. Lack of Home Presentation by Real Estate Agents

        Use these examples as a guide for formatting and specificity when creating pain point titles.

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
                safe_body = post['body'].encode('ascii', errors='ignore').decode('ascii')
                posts_str += f"""
                - POST:
                - Text: {safe_body}
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
        
        chain = chat_template | self.openai_small_llm_json | parser
        log.info("Starting Batch Pain Points")
        # Chain Invoke
        response = chain.batch(queries,config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(queries))]})
        log.info(f'Response Size:{len(response)}')
        log.info("Finished Batch Pain Points")
        return self._process_pain_points(response,EMOTION_VALUES)

    def _filter_pain_points(self,processed_pain_points):
        pain_point_dict = self._extract_pain_points_info(processed_pain_points)
        
        final_pain_point_strs = []
        final_pain_point_instruction = f'Represent the {self.space} Pain Point for Clustering'

        for pain_point,description in zip(pain_point_dict['title'],pain_point_dict['description']):
            final_pain_point_strs.append(f'{final_pain_point_instruction}:{pain_point} Description:{description}')    
        final_pain_point_embeddings = self.openai_embedder.embed_documents(final_pain_point_strs)

        return pain_point_dict,  final_pain_point_embeddings
    
    def _cluster_pain_points(self,final_filtered_dict, final_pain_point_embeddings):
        similarity_matrix = cosine_similarity(final_pain_point_embeddings)

        # Affinity Propagation clustering on similarity matrix
        affinity_model = AffinityPropagation(affinity='euclidean', random_state=42)
        affprop = affinity_model.fit(similarity_matrix)
        labels = affprop.labels_
        cluster_centers_indices = affprop.cluster_centers_indices_

        topic_dict = [
            {
                "title": title,
                "id": id_,
                "description": description,
                "link": 'https://www.reddit.com' + self.reranked_rows_dict[id_]['permalink'],
                "topic": topic_name,
                "issue": issue_name,
                "score": self.reranked_rows_dict[id_]['score'],
                "quote": quote,
                "time": self.reranked_rows_dict[id_]['created_utc'].strftime('%Y-%m-%d'),
                "persona": persona[0] if isinstance(persona, list) else persona
            }
            for title, description, id_, topic_name, issue_name, quote, persona in zip(
                final_filtered_dict['title'],
                final_filtered_dict['description'],
                final_filtered_dict['id'],
                final_filtered_dict['topic_name'],
                final_filtered_dict['issue_name'],
                final_filtered_dict['quote'],
                final_filtered_dict['persona']
            )
        ]

        # Initialize distances to centers dictionary
        distances_to_centers = {i: [] for i in range(len(cluster_centers_indices))}

        # Calculate distances to cluster centers
        for idx, label in enumerate(labels):
            center_idx = cluster_centers_indices[label]
            distance = 1 - similarity_matrix[idx, center_idx]  # Convert similarity to distance
            distances_to_centers[label].append((distance, idx))

        # Filter out items with distance greater than the threshold
        threshold = 0.2  # Adjust this value as needed (0.1 is equivalent to 0.9 similarity)
        filtered_distances_to_centers = {i: [] for i in range(len(distances_to_centers))}
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
    

    def _cluster_personas(self,persona_dict, final_persona_embeddings):
        final_persona_embeddings = np.array(final_persona_embeddings, dtype=np.float64)

        # Standardize the features
        scaler = StandardScaler()
        scaled_embeddings = scaler.fit_transform(final_persona_embeddings)

        # HDBSCAN clustering
        cluster_size  = 2 if len(scaled_embeddings) < 100 else 5
        min_samples = 1 if len(scaled_embeddings) < 100 else 3
        clusterer = hdbscan.HDBSCAN(metric='euclidean', min_cluster_size=cluster_size, min_samples=min_samples)
        labels = clusterer.fit_predict(scaled_embeddings)

        # Create topic dictionary
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
            for title, description, id_, quote in zip(
                persona_dict['title'],
                persona_dict['description'],
                persona_dict['id'],
                persona_dict['quote']
            )
        ]

        # Calculate distances to cluster exemplars and collect noise points
        filtered_distances_to_centers = {}
        noise_points = []

        for idx, (label, point) in enumerate(zip(labels, scaled_embeddings)):
            if label != -1:  # Non-noise points
                exemplar = clusterer.exemplars_[label]
                distance = np.linalg.norm(exemplar - point)
                if label not in filtered_distances_to_centers:
                    filtered_distances_to_centers[label] = []
                filtered_distances_to_centers[label].append((distance, idx))
            else:  # Noise points
                noise_points.append(idx)
        return filtered_distances_to_centers, noise_points, topic_dict
    
    def _represent_personas(self,filtered_distances_to_centers,miscellaneous_cluster,topic_dict,concurrency=3):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=ClusterPersonaAnalysis))

        system_template = """Analyze the following cluster of related items in the context of the given space. Each item represents a persona relevant to the space. Your task is to:

        Evaluate whether the items represent personas relevant to the given space and perspective. Reject clusters that are too generic, vague, or not all items match the given perspective. Reject any clusters which items don't match the space. Note: Clusters where all items have the same persona are valid and should not be rejected. 
        Determine if there's a unified theme among the items that is an exact match for the space and perspective. 
        The unified theme should either be a trait/goal/behavior that differentiates the persona inside the perspective.

        Reject clusters without a common theme without a common trait/goal/behavior.

        If a unified theme exists:
        a) Create a descriptive title for the persona (3-7 words) that identifies and describes the unique specific theme in the cluster.
        b) Select a representative quote from the cluster that best illustrates the persona
        c) Write a brief description summarizing the common persona. (1-2 sentences).
        If there's no clear unified theme or if the cluster is too generic reject it.:
        State that the cluster lacks a cohesive theme or is too generic, and briefly explain why.

        Remember to focus on the core trait of th expressed in the cluster. Avoid using specific names or identifiers mentioned in the items. Ensure that the identified persona is specific, actionable, and clearly related to user frustrations in the given space and perspective.
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
            for distance, idx in sorted(distances[:10], key=lambda x: x[0]):
                try:
                    cluster_str += f"""
                    - Persona:
                    - Title : {topic_dict[idx]['title']}
                    - Description: {topic_dict[idx]['description']}
                    - Quote: {topic_dict[idx]['quote']}
                    - Quote ID:{topic_dict[idx]['id']}
                    """
                except Exception as e:
                    log.error(f"Error representing posts persona:{e}")
            queries.append({
                "space" : self.space,
                "perspective" : self.perspective,
                "context" : self.context,
                "cluster" : cluster_str,
                "format_instructions" : parser.get_format_instructions()
            })
            cluster_indices.append(cluster)
        chain = chat_template | self.openai_small_llm_json | parser

        # Chain Invoke
        response = chain.batch(queries,config={"max_concurrency": concurrency})

        return self._create_persona_cluster(topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster)
    
    def _represent_pain_points(self,filtered_distances_to_centers,miscellaneous_cluster,topic_dict,concurrency=3):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=ClusterAnalysis))

        system_template = """Analyze the following cluster of related items in the context of the given space. Each item represents a pain point or issue experienced by users. Your task is to:

        Evaluate whether the items represent specific, concrete pain points relevant to the given space and perspective. Reject clusters that are too generic, vague, or not clearly related to user frustrations. Note: Clusters where all items discuss the same specific issue are valid and should not be rejected.
        Determine if there's a specific unified pain point among the items that fits with the given space and perspective. A unified pain point can emerge from items discussing the same specific issue or closely related issues.
        If a unified pain point exists:
        a) Create a concise, descriptive title for the pain point (3-7 words) that identifies the unique specific pain point in the cluster.
        b) Select a representative quote from the cluster that best illustrates the pain point with a negative sentiment.
        c) Write a brief description summarizing the common issue (1-2 sentences).
        If there's no clear unified theme or if the cluster is too generic (but not if all items discuss the same specific issue):
        State that the cluster lacks a cohesive pain point or is too generic, and briefly explain why.

        More specific pain point titles will be evaluated much more highly.

        Pain Point Title Guidelines:
        - Pain point titles should start with one of the following phrases:
        1. "Lack of..." (for issues related to something missing)
        2. "Difficulty in..." (for issues related to friction or challenges)
        - Ensure the title is specific and clearly communicates the issue and the topic
        - Do not use emotions as part of the pain point title.

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
            for distance, idx in sorted(distances[:10], key=lambda x: x[0]):
                try:
                    cluster_str += f"""
                    - Pain Point:
                    - Title : {topic_dict[idx]['title']}
                    - Description: {topic_dict[idx]['description']}
                    - Quote: {topic_dict[idx]['quote']}
                    - Quote ID:{topic_dict[idx]['id']}
                    """
                except Exception as e:
                    log.error(f"Error Representing Pain Points:{e}")
            queries.append({
                "space" : self.space,
                "perspective" : self.perspective,
                "context" : self.context,
                "cluster" : cluster_str,
                "format_instructions" : parser.get_format_instructions()
            })
            cluster_indices.append(cluster)
        chain = chat_template | self.openai_small_llm_json | parser

        # Chain Invoke
        response = chain.batch(queries,config={"max_concurrency": concurrency})

        return self._create_pain_point_cluster(topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster)

    def _create_persona_cluster(self,topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster):
        persona_clusters = []
        total_items = sum(len(distances) for distances in filtered_distances_to_centers.values())
        for i, cluster in enumerate(cluster_indices):
            cluster_analysis = response[i]
            if 'validCluster' in cluster_analysis and cluster_analysis['validCluster']:
                valid_cluster = cluster_analysis['validCluster']
                sub_personas = []
                distances = filtered_distances_to_centers[cluster]
                cluster_items_count = len(distances)

                for distance, idx in distances:
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
                        percentage=percentage, 
                        top_pain_points=[],
                    )
                )
        # Calculate the percentage for miscellaneous cluster
        total_items = sum(cluster.percentage for cluster in persona_clusters) 

        # Sort the clusters by percentage in descending order
        persona_clusters.sort(key=lambda x: x.percentage, reverse=True)
        # Append the miscellaneous cluster
        
        if len(persona_clusters) > 1:

            # Encode the titles and descriptions
            titles = [f'Represent the {self.space} Persona Title for Clustering Persona:{cluster.title} Description:{cluster.description}' for cluster in persona_clusters]
    
            embeddings = self.openai_embedder.embed_documents(titles)

            # Calculate Euclidean distances (converting similarities to distances)
            similarity_matrix = cosine_similarity(embeddings)

            # Convert similarities to distances
            distances = 1 - similarity_matrix

            # Perform hierarchical clustering using Ward linkage
            Z = linkage(distances[np.triu_indices(distances.shape[0], k=1)], method='average')

            # Extract clusters with a distance threshold of 0.6
            cluster_labels = fcluster(Z, t=0.07, criterion='distance')

            # Group clusters based on the labels
            clustered_personas = {}
            for idx, label in enumerate(cluster_labels):
                if label not in clustered_personas:
                    clustered_personas[label] = []
                clustered_personas[label].append(persona_clusters[idx])

            # Merge clusters within each group
            merged_clusters = []
            for label, clusters in clustered_personas.items():
                if len(clusters) > 1:
                    # Print merging information
                    log.info(f"Merging clusters with label {label}:")
                    for cluster in clusters:
                        log.info(f"  - {cluster.title} (Percentage: {cluster.percentage:.2f}%)")

                    # Merge clusters
                    merged_cluster = PersonaCluster(
                        title=clusters[0].title,
                        quote=clusters[0].quote,
                        score=clusters[0].score,
                        link=clusters[0].link,
                        time=clusters[0].time,
                        description=clusters[0].description,
                        sub_personas=[item for cluster in clusters for item in cluster.sub_personas],
                        percentage=sum(cluster.percentage for cluster in clusters),
                        top_pain_points=[]
                    )
                    merged_clusters.append(merged_cluster)

                    log.info(f"Merged into: {merged_cluster.title} (Combined Percentage: {merged_cluster.percentage:.2f}%)\n")
                else:
                    merged_clusters.append(clusters[0])

            # Recalculate percentages
            total_percentage = sum(cluster.percentage for cluster in merged_clusters)
            for cluster in merged_clusters:
                cluster.percentage = (cluster.percentage / total_percentage) * 100

            # Sort the merged clusters by percentage in descending order
            merged_clusters.sort(key=lambda x: x.percentage, reverse=True)

            # Print final cluster information
            log.info("\nFinal Persona Clusters after merging:")
            for cluster in merged_clusters:
                log.info(f"- {cluster.title} (Percentage: {cluster.percentage:.2f}%)")

            return merged_clusters[:10]
        else:
            return persona_clusters[:10]


    def _create_pain_point_cluster(self,topic_dict,response,filtered_distances_to_centers,cluster_indices,miscellaneous_cluster):
        pain_point_clusters = []
        total_items = sum(len(distances) for distances in filtered_distances_to_centers.values())

        for i, cluster in enumerate(cluster_indices):
            cluster_analysis = response[i]
            if 'validCluster' in cluster_analysis and cluster_analysis['validCluster']:
                valid_cluster = cluster_analysis['validCluster']
                sub_pain_points = []
                distances = filtered_distances_to_centers[cluster]
                cluster_items_count = len(distances)
                for distance, idx in distances:
                    try:
                        sub_pain_points.append(
                            PainPointClusterItem(
                                title=topic_dict[idx]['title'],
                                quote=topic_dict[idx]['quote'],
                                description=topic_dict[idx]['description'],
                                score=topic_dict[idx]['score'],
                                link=topic_dict[idx]['link'],
                                time=topic_dict[idx]['time'],
                                persona=topic_dict[idx]['persona']  
                            )
                        )
                    except Exception as e:
                        log.error(f'Error processing pain point:{e}')

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
        total_items = sum(cluster.percentage for cluster in pain_point_clusters)

        pain_point_clusters.sort(key=lambda x: x.percentage, reverse=True)
        if len(pain_point_clusters) > 1:
            titles = [f'Represent the {self.space} Pain Point for Clustering: {cluster.title} Description:{cluster.description}' for cluster in pain_point_clusters]
    
            embeddings = self.openai_embedder.embed_documents(titles)
            
            # Calculate cosine similarities
            distances = euclidean_distances(normalize(embeddings))
            
            # Perform hierarchical clustering using Ward linkage on the cosine similarity matrix
            Z = linkage(1 - distances, method='average')
            
            # Extract clusters with a distance threshold of 0.05
            cluster_labels = fcluster(Z, t=0.6, criterion='distance')

            # Group clusters based on the labels
            clustered_pain_points = {}
            for idx, label in enumerate(cluster_labels):
                if label not in clustered_pain_points:
                    clustered_pain_points[label] = []
                clustered_pain_points[label].append(pain_point_clusters[idx])
            
            # Merge clusters within each group
            merged_clusters = []
            for label, clusters in clustered_pain_points.items():
                if len(clusters) > 1:
                    # Print merging information
                    log.info(f"Merging clusters with label {label}:")
                    for cluster in clusters:
                        log.info(f"  - {cluster.title} (Percentage: {cluster.percentage:.2f}%)")
                    
                    # Merge clusters
                    merged_cluster = PainPointCluster(
                        title=clusters[0].title,
                        quote=clusters[0].quote,
                        score=clusters[0].score,
                        link=clusters[0].link,
                        time=clusters[0].time,
                        description=clusters[0].description,
                        sub_pain_points=[item for cluster in clusters for item in cluster.sub_pain_points],
                        percentage=sum(cluster.percentage for cluster in clusters)
                    )
                    merged_clusters.append(merged_cluster)
                    
                    log.info(f"Merged into: {merged_cluster.title} (Combined Percentage: {merged_cluster.percentage:.2f}%)\n")
                else:
                    merged_clusters.append(clusters[0])
            
            # Recalculate percentages
            total_percentage = sum(cluster.percentage for cluster in merged_clusters)
            for cluster in merged_clusters:
                cluster.percentage = (cluster.percentage / total_percentage) * 100
            
            # Sort the merged clusters by percentage in descending order
            merged_clusters.sort(key=lambda x: x.percentage, reverse=True)
            
            # Print final cluster information
            log.info("\nFinal Pain Point Clusters after merging:")
            for cluster in merged_clusters:
                log.info(f"- {cluster.title} (Percentage: {cluster.percentage:.2f}%)")
            return merged_clusters[:13]
        else:
            return pain_point_clusters[:13]
    
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
            "emotion": [],
            "persona": []
        }

        for pain_point in pain_points_model:
            if pain_point['post_id'] in self.reranked_rows_dict:
                try:
                    extracted_info["quote"].append(pain_point["quote"])
                    extracted_info["topic_name"].append(pain_point["issue_topic"]["name"])
                    extracted_info["topic_type"].append(pain_point["issue_topic"]["topic_type"])
                    extracted_info["issue_name"].append(pain_point["issue"]["name"])
                    extracted_info["issue_type"].append(pain_point["issue"]["issue_type"])
                    extracted_info["description"].append(pain_point["description"])
                    extracted_info["title"].append(pain_point['title'])
                    extracted_info["id"].append(pain_point['post_id'])
                    extracted_info["emotion"].append(pain_point["issue_emotion"])
                    extracted_info["persona"].append(pain_point["persona"])
                except Exception as e:
                    log.error(f"Error extracting pain points info: {e}")
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

        final_persona_instruction = f'Represent the {self.space} Persona Title for Clustering'
        final_persona_strs = []
        for persona,description in zip(persona_dict['title'],persona_dict['description']):
            final_persona_strs.append(f'{final_persona_instruction} Persona:{persona} Description:{description}')    
        final_persona_embeddings = self.openai_embedder.embed_documents(final_persona_strs)
        return persona_dict, final_persona_embeddings 
        
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
            final_filtered_dict, final_persona_embeddings =  self._filter_personas(processed_personas)
            log.info("Personas filtered")
            filtered_distances_to_centers, miscellaneous_cluster, topic_dict = self._cluster_personas(final_filtered_dict, final_persona_embeddings)
            log.info("Personas clustered")
            self.personas = self._represent_personas(filtered_distances_to_centers,miscellaneous_cluster,topic_dict,concurrency)
            log.info("Personas represented")
        return self.personas
        
    def _batch_personas(self,batch_size=3,concurrency=10):
        parser = ErrorJsonParser(json_parser=JsonOutputParser(pydantic_object=PersonaResponse))

        system_template = """Create up to 5 personas for users who relate to the following space and exactly match the given perspective. If no personas can be found that exactly meet the given perspective, create no personas.

        Persona Creation Guidelines:
        1. Each persona MUST be directly derived from the provided Reddit data and MUST have a highly relevant quote.
        2. Each persona MUST be relevant to the given perspective and space.
        3. Each persona MUST be unique and distinct from the others.
        4. Each persona should have a unique trait/behavior/or goal that differentiates it inside the perspective.
        6. Do not include information that is not directly related to the business context.

        Quote Requirements:
        - Each quote MUST be unique and used only ONCE.
        - Each quote MUST be directly related to the persona and given perspective.
        - DO NOT EXTRAPOLATE or modify the quotes in any way.

        Evaluation Criteria:
        1. Match perspective (Personas must be an exact match for the given perspective.)
        2. Contains a Unique trait/behavior/ or goal relevant to the perspective.

        Process:
        1. Carefully analyze the given perspective and business context.
        2. Search for relevant data in the provided Reddit information.
        3. If no data matches the perspective exactly, create no personas.
        4. If matching data is found, create personas step-by-step, ensuring each meets all requirements.
        5. Double-check that each persona and quote strictly adheres to all guidelines.

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
                safe_body = post['body'].encode('ascii', errors='ignore').decode('ascii')
                posts_str += f"""
                - POST:
                - Text: {safe_body}
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

        chain = chat_template | self.openai_small_llm_json  | parser

        # Chain Invoke
        personas_response = chain.batch(queries,config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(queries))]})

        return self._process_personas(personas_response)

    def _get_persona_pain_point(self):
        unique_personas = [persona_cluster.title for persona_cluster in self.personas]

        persona_total_counts = {persona: 0 for persona in unique_personas}

        # Create a dictionary to count pain points for each persona in each cluster
        persona_cluster_counts = {persona: defaultdict(int) for persona in unique_personas}

        # Count pain points for each persona in each cluster
        for cluster in self.pain_points:
            for sub_point in cluster.sub_pain_points:
                if sub_point.persona in unique_personas:
                    persona_cluster_counts[sub_point.persona][cluster.title] += 1
                    persona_total_counts[sub_point.persona] += 1

        # Find top 3 pain point clusters for each persona
        persona_top_clusters = {}
        for persona in self.personas:
            cluster_counts = persona_cluster_counts[persona.title]
            if cluster_counts:
                # Sort clusters by count and get top 3
                top_3_clusters = sorted(cluster_counts.items(), key=lambda x: x[1], reverse=True)[:3]
                top_clusters_info = []
                for cluster_title, count in top_3_clusters:
                    # Find the corresponding PainPointCluster object
                    cluster = next((c for c in self.pain_points if c.title == cluster_title), None)
                    if cluster:
                        # Filter sub_pain_points for this persona
                        persona_sub_points = [sp for sp in cluster.sub_pain_points if sp.persona == persona.title]
                        # Sort by score and get top 5
                        top_sub_points = sorted(persona_sub_points, key=lambda x: x.score, reverse=True)[:5]
                        
                        # Calculate the correct percentage based on total pain points for the persona
                        total_persona_points = persona_total_counts[persona.title]
                        percentage = (count / total_persona_points) * 100 if total_persona_points > 0 else 0
                        
                        # Create a new PainPointCluster object with filtered sub_pain_points
                        cluster_obj = PainPointCluster(
                            title=cluster.title,
                            quote=cluster.quote,
                            score=cluster.score,
                            time=cluster.time,
                            link=cluster.link,
                            description=f"Common issue found in {count} out of {total_persona_points} pain points for {persona.title}",
                            percentage=percentage,
                            sub_pain_points=top_sub_points
                        )
                        top_clusters_info.append(cluster_obj)
                
                persona.top_pain_points = top_clusters_info
            else:
                persona.top_pain_points = []

    def _extract_persona_info(self,personas_model):
        extracted_info = {
            "quote": [],
            "title":[],
            "description" : [],
            "link": [],
            "id": [],
        }

        for persona in personas_model:
            try:
                if persona['post_id'] in self.reranked_rows_dict:
                    extracted_info["quote"].append(persona["quote"])
                    extracted_info["description"].append(persona["description"])
                    extracted_info["title"].append(persona['title'])
                    extracted_info["id"].append(persona['post_id'])
            except Exception as e:
                log.error(f"Error extracting persona info: {e}")
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
                            log.error(f"Error processing personas: {e}")
        
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
                final_filtered_dict, final_pain_point_embeddings =  self._filter_pain_points(processed_pain_points)
                log.info("Pain points filtered")
                filtered_distances_to_centers, miscellaneous_cluster, topic_dict = self._cluster_pain_points(final_filtered_dict, final_pain_point_embeddings)
                log.info("Pain points clustered")
                self.pain_points = self._represent_pain_points(filtered_distances_to_centers,miscellaneous_cluster,topic_dict)
                log.info("Pain points represented")
                self._get_persona_pain_point()
                log.info("Persona pain points extracted")
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