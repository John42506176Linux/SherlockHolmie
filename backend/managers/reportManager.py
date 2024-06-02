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
from langchain.chat_models import ChatOpenAI
from constants import  reddit_constants
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from typing import Any
from uuid import UUID
from langchain_core.callbacks import BaseCallbackHandler
from utilities.utils import get_json_from_output
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain_core.prompts.prompt import PromptTemplate as LangPromptTemplate
from langchain_core.output_parsers import StrOutputParser
import logging.handlers
from collections import Counter

from tqdm import tqdm
import json

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
		self.progress_bar.update(1)
          
class ReportManager:
    def __init__(self,db_manager:DatabaseManager):
        self.db_manager = db_manager
        self.report_type = "Space" # TODO: Turn this into a class attribute
        self.large_json_llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest",safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_VIOLENCE: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_NONE,
        },).bind(generation_config={ "response_mime_type": "application/json"}) # TODO: Create an LLM class
        self.fast_llm = ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            model_kwargs={"temperature": 0},
        )
        self.flash_gemini_llm =  ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",safety_settings={
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_VIOLENCE: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_SEXUAL: HarmBlockThreshold.BLOCK_NONE,
        },)
        self.openai_small_llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo",max_retries=30)
        self.openai_big_llm =  ChatOpenAI(temperature=0, model="gpt-4o",max_retries=30)
        self.qa_chain = load_qa_with_sources_chain(self.fast_llm, chain_type="stuff")
        self.gemini_qa_chain = load_qa_with_sources_chain(self.large_json_llm, chain_type="stuff")
        self.space_info = None
        self.space = None
        self.top_documents = None
        self.top_texts = None
        self.pain_points = None
        self.personas = None
        self.author_texts = None

    def initialize_space(self,space,fast=True,threshold=0.55):
        if self.space_info is not None:
            log.error("Space already initialized")
            return None
        self.space_info = self.db_manager.space_search_query(space,fast,threshold)
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
        aggregated_data = {}
        # Iterate through the list and aggregate the text
        for row in self.space_info:
            author = row['author']
            body = row['body']
            
            if author  in aggregated_data:
                aggregated_data[author]['Text'] += 'Post: ' + body + ' \n '
                aggregated_data[author]['Num_Posts'] += 1
                
            else:
                aggregated_data[author] = {}
                aggregated_data[author]['Num_Posts'] = 1
                aggregated_data[author]['Text']  = 'Post: ' + body + ' \n '
                
        self.author_texts = [data['Text'] for data in aggregated_data.values()]
    
    def get_space_size(self):
        return len(self.space_info)

    def _batch_anthropic_space_pain_points(self,top_documents, batch_size=50,concurrency=3):
        all_insights = []  # Collect insights from all batches
        input_dicts = []
        for i in range(0, len(top_documents), batch_size):
            batch = top_documents[i : i + batch_size]
            prompt = """You are an entrepreneur researching the pain points users have with {refined_query}. You'll be provided with various Reddit posts related to this topic.
        
            Your Goal: Extract a comprehensive list of clear, specific pain points mentioned directly in these posts. Think step by step in getting the pain points. Do not extrapolate on pain points not mentioned. It is ok to give empty outputs if a pain point is not found.

            Output Format:

            A JSON list of dictionaries, each containing the following keys:
            *   **Reasoning(string):** Show how the quote clearly and unambiguously demonstrates the pain point. If it does not, please end the json there. Ensure proper escaping of double quotes (`\"`).
            *   **PainPoint (string):** The concise, descriptive title of the pain point.
            *   **Description (string):** A detailed explanation of the pain point, elaborating on its impact and implications.
            *   **Quote (string):** A verbatim excerpt from the Reddit posts that clearly illustrates the pain point. Ensure proper escaping of double quotes (`\"`).
            *   **Link (string):** The direct link to the specific comment or post containing the quote, you can only use te same link once.
            *   **Time (string):** The timestamp of the comment or post. Format: YYYY-MM-DD HH:MM:SS

            Requirements:

            *   **Limit:** Include a maximum of 3 pain points per output list.
            *   **Quality:** Each pain point must be:
                *   **Relevant:** The quote must directly and unambiguously reflect the pain point, do not include ambiguos pain points.
                *   **Specific:** Avoid vague or general statements. Clearly define the issue.
                *   **Directional:** Use action-oriented language to convey the nature of the problem (e.g., "Difficulty in...", "Lack of...").
                *   **Readable:** Write in clear, concise language, avoiding jargon and overly technical terms.
                *   **Accurate:** Faithfully represent the pain points expressed in the Reddit posts.
            
            **Reddit-Specific Exclusions:**

            DO NOT INCLUDE pain points that are exclusively relevant to Reddit's platform or user experience (e.g., issues with subreddits, karma, or site features).

            Evaluation Criteria:

            *   Relevance is the top priority. If a quote does not strongly and unambiguosly support the pain point, it should not be included.
            *   Specificity, directionality, readability, and accuracy are all important factors in determining the overall quality of each pain point.

        The response format should be JSON enclosed within the following tags: `<json></json>`

            **Here's an example:**
            <json>
            {
            "PainPoints": [
            {
            "PainPoint": "Pain Point title",
            "Description": "Pain Point Description",
            "Reasoning": "Reasoning on how pain point was derived from quote"
            "Quote": "Quote representing pain point in given data",
            "Link": "Link to quote in the given data",
            "Time": "2023-10-13 16:38:19"
            }
            ]
            }
            </json>
            

            Your output must be in JSON format only. Any additional input will be penalized.

                """
                
            prompt = prompt.replace("{space}", self.space)
            input_dict = {"question": prompt, "input_documents": batch}
            input_dicts.append(input_dict)

        insights = self.qa_chain.batch(input_dicts, config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(input_dicts))]})
        for insights_str in insights:
            try:
                insights = get_json_from_output(insights_str['output_text'])
                all_insights.extend(insights)
            except Exception as e:
                print(f"Error decoding JSON in batch starting at index {i}: {e}")
                # Handle the error (e.g., skip this batch, log the issue)
        return all_insights
    
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
    
        
    def _quantify_pain_points(self,concurrency=2):
        if self.pain_points is None:
            log.error("Pain points not initialized")
            return None
        if self.pain_points == []:
            log.error("No pain points found")
            return None
        if "Percentage" in self.pain_points[0]:
            log.error("Pain points already quantified")
            return None
        
        new_pain_point_summarized = self.pain_points.copy()
        new_pain_point_summarized.append({"Pain Point": "None", "Quote": "I just finished reading this book and I absolutely loved it! The characters were so well-developed and the plot was really engaging. I couldn't put it down!"})

        examples = [{"query": f"Text: \"{item['Quote']}\"\n", "answer": f"[{item['Pain Point']}]<Finish>"} for index, item in enumerate(new_pain_point_summarized)]

        # Create the base prompt
        pain_points = "\n".join([f"{index+1}. {item['Pain Point']}" for index, item in enumerate(new_pain_point_summarized)])

        prefix = f"""I have a reddit post/comment and I want to know if the user is expressing one of the following pain points in the following space: {{refined_query}}.

        {pain_points}


        Finish Response with <Finish>
        If they are expressing one or more of the above pain points, respond with the pain point names. If they are not expressing a pain point respond with [None].
        Respond with a list of pain points. 
        ALWAYS USE [] even for a single pain point, or None.
        """
        prefix = prefix.replace("{refined_query}", self.space)
        suffix = """
        User: {query}
        AI: """

        # create a prompt example from above template
        example_prompt = LangPromptTemplate(
            input_variables=["query", "answer"], template="User: {query}\nAI: {answer}"
        )

        few_shot_prompt_template = FewShotPromptTemplate(
            examples=examples,
            example_prompt=example_prompt,
            prefix=prefix,
            suffix=suffix,
            input_variables=["query"],
            example_separator="\n\n"
        )
        chain = few_shot_prompt_template | self.openai_small_llm | StrOutputParser()
        input_dicts = [{"query": reddit_post}  for reddit_post in self.top_texts]
        
        insights = chain.batch(input_dicts, stop=["<Finish>"], config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(input_dicts))]})
        count_dict = self._count_strings(insights)
        total_pain_point = 0
        log.info(f"Count Dict: {count_dict}")
        for pain_point in self.pain_points:
            total_pain_point += count_dict[pain_point['Pain Point']]
        for pain_point in self.pain_points:
            pain_point['Percentage'] = round((count_dict[pain_point['Pain Point']] / total_pain_point) * 100, 2)
        return self.pain_points
    
    def get_personas(self,quantify=True):
        if self.space is None:
            log.error("Space not initialized")
            return None
        if self.top_documents is None:
            log.error("Top documents not initialized")
            return None
        if self.personas is not None:
            log.error("Personas already initialized")
            return None
        prompt = f"""Create concise 3-5 personas for users who relate to the following space -- {self.space} -- based on the given Reddit data.
        Think step by step in the persona creation process.
        These personas will be evaluated on:
        - Relation to the query (Personas should be relevant to the query)
        - Persona Divergence (The personas should not be semantically different from each other in relation to the query)
        - Persona Diversity (The personas should adequately represent the users who relate to the query)
        - Consumer Relevance (The personas should be relevant to entrepreneurs who want to understand this space)

        Requirements:
        - No quote should be used more than ONCE, and each quote should be relevant to the pain point and persona and should be longer than 20 words.
        - DO NOT EXTRAPOLATE the quotes; they should be directly related to the persona or pain point they are describing.
        - Provide the personas in JSON format with the following structure:
        {{
        "personas": [
            {{
            "persona_title": "The title of the persona. Example: The Newbie Lifter",
            "persona_reasoning": "Reasoning for why the quote unambiguously connects to the persona.",
            "description": "This is a description of the persona. Example: New to exercise and weightlifting, often unsure about proper form, intensity, and pain management. May have misconceptions about exercise needing to be painful.",
            "quote": "This is a quote",
            "link": "https://www.reddit.com/r/subreddit/comments/comment_id",
            "latest_quote_time": "2023-12-12",
            "top_pain_points": [
                {{
                "pain_point_title": "This is the title of the pain point",
                "pain_point_reasoning": "Reasoning for why the quote unambiguously connects to the pain point.",
                "pain_point_description": "This is the description of the pain point",
                "pain_point_quote": "This is a quote about a pain point",
                "pain_point_link": "https://www.reddit.com/r/subreddit/comments/comment_id"
                }}
            ]
            }}
        ]
        }}

        Here is an example:
        {{
        "personas": [
            {{
            "persona_title": "The Newbie Lifter",
            "quote": "Am I literally the only person who thought exercise had to be painful?",
            "link": "https://www.reddit.com/r/xxfitness/comments/x8c5t0/wait_are_you_not_supposed_to_be_in_pain/",
            "latest_quote_time": "2022-09-07",
            "description": "New to exercise and weightlifting, often unsure about proper form, intensity, and pain management. May have misconceptions about exercise needing to be painful.",
            "top_pain_points": [
                {{
                "pain_point_title": "Fear of injury",
                "pain_point_reasoning": "The quote highlights the user's fear and experience of stopping exercise due to pain.",
                "pain_point_description": "Fear of injury and pain from exercising.",
                "pain_point_quote": "I'm not somebody who exercises for fun, and every time I've tried to get into it I've stopped because, well, it hurts.",
                "pain_point_link": "https://www.reddit.com/r/xxfitness/comments/x8c5t0/wait_are_you_not_supposed_to_be_in_pain/"
                }}
            ]
            }},
            {{
            "persona_title": "The Injury-Prone Athlete",
            "quote": "Have others had to sort of readjust their whole attitude and philosophy to exercise in general as they have gotten older?",
            "link": "https://www.reddit.com/r/xxfitness/comments/10b145x/feeling_really_lost_in_my_general_approach_to/",
            "latest_quote_time": "2023-01-13",
            "description": "Previously athletic and active, but now experiencing recurring injuries, potentially due to age, overuse, or improper form. Seeking ways to modify training and prevent further setbacks.",
            "top_pain_points": [
                {{
                "pain_point_title": "Recurring injuries hindering progress",
                "pain_point_reasoning": "The quote reflects the user's struggle with ongoing injuries affecting their activities.",
                "pain_point_description": "Persistent injuries impacting exercise routine.",
                "pain_point_quote": "I now have osteoarthritis and a recurring Baker's cyst in the knee, all stemming from poor form and overuse in volleyball.",
                "pain_point_link": "https://www.reddit.com/r/xxfitness/comments/10b145x/feeling_really_lost_in_my_general_approach_to/"
                }}
            ]
            }},
            {{
            "persona_title": "The Overtrained Enthusiast",
            "quote": "Is it excessive or even obsessive to workout for at least 1.5-2 hours a day, 6x/week?",
            "link": "https://www.reddit.com/r/xxfitness/comments/uwnsb4/how_much_exercise_is_too_much_bonus_being/",
            "latest_quote_time": "2022-05-24",
            "description": "Highly motivated and dedicated to exercise, but may be overtraining and at risk of burnout or injury. Seeking validation and information about healthy exercise habits.",
            "top_pain_points": [
                {{
                "pain_point_title": "Potential for overtraining and burnout",
                "pain_point_reasoning": "The quote expresses the user's uncertainty about the intensity and frequency of their workouts.",
                "pain_point_description": "Risk of overtraining and physical exhaustion.",
                "pain_point_quote": "...My past self would say 'holy moley that's a lot' but as I've eased myself into it, it doesn't feel like that much.",
                "pain_point_link": "https://www.reddit.com/r/xxfitness/comments/uwnsb4/how_much_exercise_is_too_much_bonus_being/"
                }}
            ]
            }},
            {{
            "persona_title": "The Chronically Sore Individual",
            "quote": "As the title says, I'm 35 but feel 65.",
            "link": "https://www.reddit.com/r/fitness30plus/comments/1akrat7/im_35_and_everything_hurts_making_a_complete/",
            "latest_quote_time": "2024-02-07",
            "description": "Experiences chronic pain and discomfort, potentially due to past injuries, inactivity, or underlying conditions. Seeking ways to improve overall health and reduce pain through exercise.",
            "top_pain_points": [
                {{
                "pain_point_title": "Chronic pain limiting activity and quality of life",
                "pain_point_reasoning": "The quote highlights the user's struggle with ongoing chronic pain affecting their daily activities.",
                "pain_point_description": "Persistent pain impacting daily life and exercise routine.",
                "pain_point_quote": "Plantar fasciitis, Chronic knee pain, Shoulder tendonitis, Tennis elbow, Chronic lower back pain, Ulnar nerve impingement",
                "pain_point_link": "https://www.reddit.com/r/fitness30plus/comments/1akrat7/im_35_and_everything_hurts_making_a_complete/"
                }}
            ]
            }},
            {{
            "persona_title": "The Desk Job Warrior",
            "quote": "Unfortunately, I sit all day for my job which means my back muscles are very prone to being tight (I’m a software engineer).",
            "link": "https://www.reddit.com/r/Fitness/comments/19519h2/consistently_injuring_my_lower_back/",
            "latest_quote_time": "2024-01-12",
            "description": "Leads a sedentary lifestyle due to a desk job, experiencing stiffness, muscle imbalances, and potential for injury. Seeking ways to incorporate exercise and improve posture and mobility.",
            "top_pain_points": [
                {{
                "pain_point_title": "Increased risk of injury due to inactivity",
                "pain_point_reasoning": "The quote shows the user's experience with injuries resulting from a sedentary lifestyle.",
                "pain_point_description": "Higher risk of injuries from inactivity and sudden physical exertion.",
                "pain_point_quote": "...I have caused myself two minor lower back injuries during lifts...",
                "pain_point_link": "https://www.reddit.com/r/Fitness/comments/19519h2/consistently_injuring_my_lower_back/"
                }}
            ]
            }}
        ]
        }}
        """

        # Generate insights using the question-answering chain with the top 10 most similar texts as context

        insights = json.loads(self.gemini_qa_chain.run(input_documents=self.top_documents[:1500], question=prompt))["personas"]
        self.personas = insights
        if "Percentage" not in self.personas[0] and quantify:
            log.info("Starting quantification of personas")
            self.personas = self._quantify_personas()
            log.info("Personas quantified")
        return insights 
    
    def _quantify_personas(self,concurrency=2):
        examples = [{"query": f"Post: \"{item['quote']}\"\n", "answer": f"[{item['persona_title']}]<Finish>"} for index, item in enumerate(self.personas)]

        # Create the base prompt
        personas_list = "\n".join([f"{index+1}. {item['persona_title']}\nPersona Description:{item['description']}" for index, item in enumerate(self.personas)])

        prefix = f"""I have a set of reddit posts/comments discussing the space '{{refined_query}}' from a single reddit user. I want to know if the author falls into one of the following personas:

    {personas_list}


        Finish Response with <Finish>
        If they do not fall into the persona categories respond with [None].
        Only respond with the persona name.
        Here are some examples
        """

        prefix = prefix.replace("{refined_query}", self.space)
        suffix = """
        User: {query}
        AI: """
        
        example_prompt = LangPromptTemplate(
            input_variables=["query", "answer"], template="User: {query}\nAI: {answer}"
        )

        few_shot_prompt_template = FewShotPromptTemplate(
            examples=examples,
            example_prompt=example_prompt,
            prefix=prefix,
            suffix=suffix,
            input_variables=["query"],
            example_separator="\n\n"
        )
        chain = few_shot_prompt_template | self.flash_gemini_llm | StrOutputParser()
        input_dicts = [{"query": reddit_post}  for reddit_post in self.author_texts]
        
        insights = chain.batch(input_dicts, stop=["<Finish>"], config={"max_concurrency": concurrency,"callbacks": [BatchCallback(len(input_dicts))]})
        count_dict = self._count_strings(insights)
        total_persona = 0
        for persona in self.personas:
            total_persona += count_dict[persona['persona_title']]
        for persona in self.personas:
            persona['Percentage'] = round((count_dict[persona['persona_title']] / total_persona) * 100, 2)
        return self.personas

    def _summarize_pain_points(self,pain_points_json):
        prefix = """
            You are an entrepreneur seeking to summarize user pain points in the {refined_query} space. You will be provided with a list of JSON objects, each containing a pain point mentioned by users.

            **JSON Object Format:**

            *   **Pain Point (string):** A concise, descriptive title of the pain point.
            *   **Description (string):** A detailed explanation of the pain point.
            *   **Reasoning (string):** Explains how the quote connects to the pain point.
            *   **Quote (string):** A direct user quote exemplifying the pain point.
            *   **Link (string):** A hyperlink to the source of the quote.
            *   **Time (string):** The timestamp of the quote.

            **Your Task:**

            1.  **Analyze and Group:** Carefully examine the pain points and group them into distinct categories based on their underlying themes and similarities.
            2.  **Resolve Overlaps:** If a pain point fits into multiple categories, prioritize assigning it to the most relevant category. If it significantly contributes to multiple categories, you may split it into sub-points or create a new, more specific category.
            4.  **Refine and Condense:** Aim to present between 5 and 7 distinct, high-level pain point categories. Ensure each category encompasses a broad range of related issues while avoiding overlap.
            
            **Evaluation Criteria:**

            *   **Individual Pain Points:**
                *   **Specificity:** Prioritize clear, focused pain point titles over vague or overly broad ones.
                *   **Directionality:** Use action-oriented language (e.g., "Difficulty in...", "Lack of...") to convey the nature of the pain point and guide sentiment analysis.
                *   **Readability:** Avoid jargon and technical terms unless they are essential to understanding the pain point.
                *   **Accuracy:** Ensure the pain points accurately and comprehensively represent the issues found in the provided data.
            *   **Overall Pain Point Categories:**
                *   **Breadth:** Cover the full spectrum of pain points present in the data.
                *   **Non-Redundancy:** Avoid duplicating or restating the same pain points across the same category. DO NOT INCLUDE THE SAME PAIN POINT TWICE.
                *   **Actionability:** Frame pain points in a way that suggests potential solutions or areas for improvement.

            **Reddit-Specific Exclusions:**

            Refrain from including pain points that are exclusively relevant to Reddit's platform or user experience (e.g., issues with subreddits, karma, or site features).

            **Output Format:**

            A JSON list of objects, each following this structure:
            
            *   **Pain Point (string):** The title of the pain point.
            *   **Description (string):** A detailed description of the pain point.
            *   **Quote (string):** A representative user quote.
            *   **Link (string):** The source link for the quote.
            *   **Time (string):** The timestamp of the quote.

            **Example Output (Illustrative, Not Exhaustive):**

            ```json
            "PainPoints": [
            {{
                "Pain Point": "Difficulty Navigating Complex Financial Products",
                "Description": "Users struggle to understand the intricacies of various investment options and financial instruments.",
                "Quote": "I'm overwhelmed by all the different choices and jargon.",
                "Link": "[invalid URL removed]",
                "Time": "2024-01-15 10:32:45",
            }},
            ]
            Here are some examples:
            """
        examples = [
            {
                "query": """
        [
            {{
                "Pain Point": "Lack of Widespread Adoption and Acceptance of Cryptocurrencies",
                "Description": "Cryptocurrencies are still not widely accepted as a form of payment, limiting their usefulness as a currency and making it difficult for users to utilize them in everyday transactions.",
                "Quote": "It's a form of money. A form that isn't universally accepted and is extremely volatile",
                "Link": "/r/Money/comments/16kjwue/do_you_consider_crypto_money/k0wkw5w/",
                "Time": "2023-09-16 23:14:54"
            }},
            {{
                "Pain Point": "Frustration with Bank Freezing Cryptocurrency Transactions",
                "Description": "Users express frustration with banks freezing or blocking their cryptocurrency transactions, leading to difficulties in cashing out their crypto profits and accessing their funds.",
                "Quote": "I've found myself in a situation where i've made some decent profits from my portfolio and when it came to me cashing out a chunk of near enough 100k, my bank was quick to block the transaction and freeze my account. The guys at the bank have not been helpful at all, feeling like they're avoiding answering my questions.",
                "Link": "/r/Money/comments/1bvywty/crypto_is_part_of_the_future_or_its_coming_to_an/",
                "Time": "2024-04-04 21:06:55"
            }},
            {{
                "Pain Point": "Concerns about Security and Fraud in Cryptocurrency Exchanges",
                "Description": "The content suggests that there are concerns about the security and potential for fraud in cryptocurrency exchanges, which may be a pain point for users.",
                "Quote": "No seriously. Avoid centralized exchanges.",
                "Link": "/r/passive_income/comments/xtpu13/how_to_build_passive_income/iqs1cxb/",
                "Time": "2022-10-02 18:00:18"
            }},
            {{
                "Pain Point": "Volatility and Uncertainty in Cryptocurrency Investments",
                "Description": "Users express concerns about the high volatility and unpredictability of cryptocurrency investments, making it challenging to reliably generate passive income or long-term wealth.",
                "Quote": "Crypto spam. Removed.",
                "Link": "/r/povertyfinance/comments/mnv9n9/my_job_restaurant_manager_is_paying_57kyear/gu27egn/",
                "Time": "2021-04-10 17:13:50"
            }},
            {{
                "PainPoint": "Concerns about the Sustainability of Cryptocurrency-based Passive Income",
                "Description": "Users express concerns about the long-term sustainability of passive income opportunities in the cryptocurrency space, particularly related to the volatility and risks involved.",
                "Quote": "Sell your crypto",
                "Link": "/r/Money/comments/1bqz9sk/broke_and_im_over_100k_in_credit_card_debt_what/kx90c9c/",
                "Time": "2024-03-30 13:24:03"
            }},
            {{
                "Pain Point": "Lack of Mainstream Adoption and Utility of Cryptocurrencies",
                "Description": "Cryptocurrencies are still not widely adopted or integrated into daily life, and their future as a mainstream currency is uncertain.",
                "Quote": "How much time has there been cryptos around? How many uses do they have in your daily life? They are becoming the past, not the future.",
                "Link": "/r/Money/comments/1bvywty/crypto_is_part_of_the_future_or_its_coming_to_an/ky2ubmu/",
                "Time": "2024-04-04 21:40:25"
            }},
            {{
                "Pain Point": "Difficulty in Identifying Legitimate Cryptocurrency Projects",
                "Description": "With the proliferation of various cryptocurrency projects, it can be challenging for users to distinguish legitimate and promising projects from potential scams or low-quality investments. Users need guidance on how to evaluate the credibility and potential of different cryptocurrency offerings.",
                "Quote": "The thing about crypto, I have heard about all these coins, and icos that a lot end up being scams, and the owners run off with investors monies etc. How do you know you can trust a coin?",
                "Link": "/r/passive_income/comments/lyamtq/just_got_2_jobs_within_3_days_can_someone_help_me/gqnjd9h/",
                "Time": "2021-03-12 03:44:44"
            }},
            {{
                "Pain Point": "Lack of Relevant Cryptocurrency Discussions",
                "Description": "Users express frustration that cryptocurrency discussions are often not allowed or are considered off-topic in certain subreddits, leading to a lack of relevant places to discuss the topic.",
                "Quote": "Discussion around specific cryptocurrency is outside the scope of this subreddit. Try /r/CryptoCurrency instead.",
                "Link": "/r/FinancialPlanning/comments/p48i24/question_about_emergency_fund/h8wxmvm/",
                "Time": "2021-08-14 14:35:42"
            }}
        ]
        """,
                "answer": """
            "PainPoints": [
                {{
                    "Pain Point": "Lack of Widespread Adoption and Acceptance of Cryptocurrencies",
                    "Description": "Cryptocurrencies are still not widely accepted as a form of payment, limiting their usefulness as a currency and making it difficult for users to utilize them in everyday transactions.",
                    "Quote": "It's a form of money. A form that isn't universally accepted and is extremely volatile",
                    "Link": "/r/Money/comments/16kjwue/do_you_consider_crypto_money/k0wkw5w/",
                    "Time": "2023-09-16 23:14:54",
                }},
                {{
                    "Pain Point": "Frustration with Bank Freezing Cryptocurrency Transactions",
                    "Description": "Users express frustration with banks freezing or blocking their cryptocurrency transactions, leading to difficulties in cashing out their crypto profits and accessing their funds.",
                    "Quote": "I've found myself in a situation where i've made some decent profits from my portfolio and when it came to me cashing out a chunk of near enough 100k, my bank was quick to block the transaction and freeze my account. The guys at the bank have not been helpful at all, feeling like they're avoiding answering my questions.",
                    "Link": "/r/Money/comments/1bvywty/crypto_is_part_of_the_future_or_its_coming_to_an/",
                    "Time": "2024-04-04 21:06:55",
                }},
                {{
                    "Pain Point": "Concerns about the Sustainability of Cryptocurrency-based Passive Income",
                    "Description": "Users express concerns about the long-term sustainability of passive income opportunities in the cryptocurrency space, particularly related to the volatility and risks involved.",
                    "Quote": "Sell your crypto",
                    "Link": "/r/Money/comments/1bqz9sk/broke_and_im_over_100k_in_credit_card_debt_what/kx90c9c/",
                    "Time": "2024-03-30 13:24:03",
                }},
                {{
                    "Pain Point": "Difficulty in Identifying Legitimate Cryptocurrency Projects",
                    "Description": "With the proliferation of various cryptocurrency projects, it can be challenging for users to distinguish legitimate and promising projects from potential scams or low-quality investments. Users need guidance on how to evaluate the credibility and potential of different cryptocurrency offerings.",
                    "Quote": "The thing about crypto, I have heard about all these coins, and icos that a lot end up being scams, and the owners run off with investors monies etc. How do you know you can trust a coin?",
                    "Link": "/r/passive_income/comments/lyamtq/just_got_2_jobs_within_3_days_can_someone_help_me/gqnjd9h/",
                    "Time": "2021-03-12 03:44:44",
                }}
            ]
            """
            },
            {
                "query": """
        [
            {{
                "Pain Point": "Lack of Widespread Adoption and Acceptance of Cryptocurrencies",
                "Description": "Cryptocurrencies are still not widely accepted as a form of payment, limiting their usefulness as a currency and making it difficult for users to utilize them in everyday transactions.",
                "Quote": "It's a form of money. A form that isn't universally accepted and is extremely volatile",
                "Link": "/r/Money/comments/16kjwue/do_you_consider_crypto_money/k0wkw5w/",
                "Time": "2023-09-16 23:14:54"
            }},
            {{
                "Pain Point": "Frustration with Bank Freezing Cryptocurrency Transactions",
                "Description": "Users express frustration with banks freezing or blocking their cryptocurrency transactions, leading to difficulties in cashing out their crypto profits and accessing their funds.",
                "Quote": "I've found myself in a situation where i've made some decent profits from my portfolio and when it came to me cashing out a chunk of near enough 100k, my bank was quick to block the transaction and freeze my account. The guys at the bank have not been helpful at all, feeling like they're avoiding answering my questions.",
                "Link": "/r/Money/comments/1bvywty/crypto_is_part_of_the_future_or_its_coming_to_an/",
                "Time": "2024-04-04 21:06:55"
            }},
            {{
                "Pain Point": "Concerns about Security and Fraud in Cryptocurrency Exchanges",
                "Description": "The content suggests that there are concerns about the security and potential for fraud in cryptocurrency exchanges, which may be a pain point for users.",
                "Quote": "No seriously. Avoid centralized exchanges.",
                "Link": "/r/passive_income/comments/xtpu13/how_to_build_passive_income/iqs1cxb/",
                "Time": "2022-10-02 18:00:18"
            }},
            {{
                "Pain Point": "Volatility and Uncertainty in Cryptocurrency Investments",
                "Description": "Users express concerns about the high volatility and unpredictability of cryptocurrency investments, making it challenging to reliably generate passive income or long-term wealth.",
                "Quote": "Crypto spam. Removed.",
                "Link": "/r/povertyfinance/comments/mnv9n9/my_job_restaurant_manager_is_paying_57kyear/gu27egn/",
                "Time": "2021-04-10 17:13:50"
            }},
            {{
                "Pain Point": "Concerns about the Sustainability of Cryptocurrency-based Passive Income",
                "Description": "Users express concerns about the long-term sustainability of passive income opportunities in the cryptocurrency space, particularly related to the volatility and risks involved.",
                "Quote": "Sell your crypto",
                "Link": "/r/Money/comments/1bqz9sk/broke_and_im_over_100k_in_credit_card_debt_what/kx90c9c/",
                "Time": "2024-03-30 13:24:03"
            }},
            {{
                "Pain Point": "Lack of Mainstream Adoption and Utility of Cryptocurrencies",
                "Description": "Cryptocurrencies are still not widely adopted or integrated into daily life, and their future as a mainstream currency is uncertain.",
                "Quote": "How much time has there been cryptos around? How many uses do they have in your daily life? They are becoming the past, not the future.",
                "Link": "/r/Money/comments/1bvywty/crypto_is_part_of_the_future_or_its_coming_to_an/ky2ubmu/",
                "Time": "2024-04-04 21:40:25"
            }},
            {{
                "Pain Point": "Difficulty in Identifying Legitimate Cryptocurrency Projects",
                "Description": "With the proliferation of various cryptocurrency projects, it can be challenging for users to distinguish legitimate and promising projects from potential scams or low-quality investments. Users need guidance on how to evaluate the credibility and potential of different cryptocurrency offerings.",
                "Quote": "The thing about crypto, I have heard about all these coins, and icos that a lot end up being scams, and the owners run off with investors monies etc. How do you know you can trust a coin?",
                "Link": "/r/passive_income/comments/lyamtq/just_got_2_jobs_within_3_days_can_someone_help_me/gqnjd9h/",
                "Time": "2021-03-12 03:44:44"
            }},
            {{
                "Pain Point": "Lack of Relevant Cryptocurrency Discussions",
                "Description": "Users express frustration that cryptocurrency discussions are often not allowed or are considered off-topic in certain subreddits, leading to a lack of relevant places to discuss the topic.",
                "Quote": "Discussion around specific cryptocurrency is outside the scope of this subreddit. Try /r/CryptoCurrency instead.",
                "Link": "/r/FinancialPlanning/comments/p48i24/question_about_emergency_fund/h8wxmvm/",
                "Time": "2021-08-14 14:35:42"
            }}
        ]
        """,
                "answer": """
            "PainPoints": [
                {{
                    "Pain Point": "Lack of Widespread Adoption and Acceptance of Cryptocurrencies",
                    "Description": "Cryptocurrencies are still not widely accepted as a form of payment, limiting their usefulness as a currency and making it difficult for users to utilize them in everyday transactions.",
                    "Quote": "It's a form of money. A form that isn't universally accepted and is extremely volatile",
                    "Link": "/r/Money/comments/16kjwue/do_you_consider_crypto_money/k0wkw5w/",
                    "Time": "2023-09-16 23:14:54",
                }},
                {{
                    "Pain Point": "Frustration with Bank Freezing Cryptocurrency Transactions",
                    "Description": "Users express frustration with banks freezing or blocking their cryptocurrency transactions, leading to difficulties in cashing out their crypto profits and accessing their funds.",
                    "Quote": "I've found myself in a situation where i've made some decent profits from my portfolio and when it came to me cashing out a chunk of near enough 100k, my bank was quick to block the transaction and freeze my account. The guys at the bank have not been helpful at all, feeling like they're avoiding answering my questions.",
                    "Link": "/r/Money/comments/1bvywty/crypto_is_part_of_the_future_or_its_coming_to_an/",
                    "Time": "2024-04-04 21:06:55",
                }},
                {{
                    "Pain Point": "Concerns about the Sustainability of Cryptocurrency-based Passive Income",
                    "Description": "Users express concerns about the long-term sustainability of passive income opportunities in the cryptocurrency space, particularly related to the volatility and risks involved.",
                    "Quote": "Sell your crypto",
                    "Link": "/r/Money/comments/1bqz9sk/broke_and_im_over_100k_in_credit_card_debt_what/kx90c9c/",
                    "Time": "2024-03-30 13:24:03",
                }},
                {{
                    "Pain Point": "Difficulty in Identifying Legitimate Cryptocurrency Projects",
                    "Description": "With the proliferation of various cryptocurrency projects, it can be challenging for users to distinguish legitimate and promising projects from potential scams or low-quality investments. Users need guidance on how to evaluate the credibility and potential of different cryptocurrency offerings.",
                    "Quote": "The thing about crypto, I have heard about all these coins, and icos that a lot end up being scams, and the owners run off with investors monies etc. How do you know you can trust a coin?",
                    "Link": "/r/passive_income/comments/lyamtq/just_got_2_jobs_within_3_days_can_someone_help_me/gqnjd9h/",
                    "Time": "2021-03-12 03:44:44",
                }}
            ]
            """
            },
            
        ]
        prefix = prefix.replace("{refined_query}", self.space)
        suffix = """
        User: {query}
        AI: """

        # create a prompt example from above template
        example_prompt = LangPromptTemplate(
            input_variables=["query", "answer"], template="User: {query}\nAI: {answer}"
        )

        few_shot_prompt_template = FewShotPromptTemplate(
            examples=examples,
            example_prompt=example_prompt,
            prefix=prefix,
            suffix=suffix,
            input_variables=["query"],
            example_separator="\n\n"
        )
        chain = few_shot_prompt_template | self.openai_big_llm | StrOutputParser()

        # Chain Invoke
        response = chain.invoke({"query": json.dumps(pain_points_json)})
        return response 

    def get_pain_points(self,batch_size=50,quantify=True):
        if self.space_info is None :
            raise Exception("Space not initialized")
        elif batch_size < 1 or batch_size > 200:
            raise Exception("Batch size must be between 1 and 200")
        else:
            log.info("Starting pain point extraction")
            if self.pain_points is None:
                pain_points = self._batch_anthropic_space_pain_points(self.top_documents,batch_size)
                log.info("Pain points extracted")
                self.pain_points =  json.loads(self._summarize_pain_points(pain_points))["PainPoints"]
                log.info("Pain points summarized")
            if "Percentage" not in self.pain_points[0] and quantify:
                log.info("Starting quantification of pain points")
                self.pain_points = self._quantify_pain_points()
                log.info("Pain points quantified")
            return self.pain_points