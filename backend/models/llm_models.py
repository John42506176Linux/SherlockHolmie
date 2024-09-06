from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
from typing import Optional, Tuple,List

class EmotionType(str, Enum):
    CONCERN = "Concern"
    FRUSTRATION = "Frustration"
    CONFUSION = "Confusion"
    ANGER = "Anger"
    NEUTRAL = "Neutral"
    DISAPPOINTMENT = "Disappointment"
    HOPE = "Hope"
    EXCITEMENT = "Excitement"
    RELIEF = "Relief"
    SATISFACTION = "Satisfaction"
    ANXIETY = "Anxiety"
    FEAR = "Fear"
    DISGUST = "Disgust"
    RESENTMENT = "Resentment"
    SYMPATHY = "Sympathy"
    ADMIRATION = "Admiration"
    OPTIMISM = "Optimism"
    TRUST = "Trust"
    CURIOSITY="Curiosity"
    JOY = "Joy"
    GRATITUDE = "Gratitude"
    SURPRISE = "Surprise"
    SADNESS = "Sadness"
    BOREDOM = "Boredom"
    EMBARRASSMENT = "Embarrassment"
    ENVY = "Envy"
    PRIDE = "Pride"
    ANTICIPATION="Anticipation"
    APPREHENSION="Apprehension"
    DISTRUST="Distrust"
    WORRY="Worry"
    WARINESS="Wariness"
    SKEPTICISM="Skepticism"
        
class GivenUserPerspective(BaseModel):
    name: str = Field(description="What is the perspective the user is requesting?")
    location: Optional[str] = Field(description='The location the user is requesting in the perspective. Only add a location if the user clearly asked for a location. Do not make assumptions. Use null, if the location was not requested.')
    location_weight: float = Field(..., ge=0, le=1, description="How important you think the location is to the perspective. If the user doesn't mention a location, or location is null. This should be 0.0. If they do it should be a number from 0 - 1, depending on how important you think location is in relation to all the other attributes.")
    occupation: Optional[str] = Field(description="The occupation the user is requesting in the perspective. Only add an occupation if the user clearly asked for an occupation. Do not make assumptions. Use null, if the occupation was not requested.")
    occupation_weight: float = Field(..., ge=0, le=1, description="How important you think the occupation is to the perspective. If the user doesn't mention an occupation, or occupation is null. This should be 0.0. This should be 0.0. If they do it should be a number from 0 - 1, depending on how important you think occupation is in relation to all the other attributes.")
    consumed_product:Optional[str] = Field(description='The product/service/process the user is requesting the user be a consumer of in the perspective. Only add a consumed product, if the user clearly asked for a consumed product. Do not make assumptions. Use null, if the consumed product was not requested.')
    consumed_product_weight: float = Field(..., ge=0, le=1, description="How important you think the consumer product is to the perspective. If the user doesn't mention a consumed product, or consumed product is null. This should be 0.0. This should be 0.0. If they do it should be a number from 0 - 1, depending on how important you think consumed product is in relation to all the other attributes.")
        
class TopicType(str,Enum):
    PRODUCT ="Product"
    PRODUCT_FEATURE= "Product Feature"
    PRODUCT_PROCESS = "Product Process"
    PROCESS="Process"
    GEOGRAPHY="Geography"
    INDUSTRY="Industry"
    PERSONA="Persona"
    OCCUPATION="Occupation"  
    DEMOGRAPHICS="Demographics"
    OTHER="Other"

class IssueType(str, Enum):
    QUALITY = "Quality"
    USABILITY = "Usability"
    SAFETY = "Safety"
    MAINTENANCE = "Maintenance"
    COST = "Cost"
    INNOVATION = "Innovation"
    SUPPLY_CHAIN = "Supply Chain"
    EFFICIENCY = "Efficiency"
    ACCURACY = "Accuracy"
    COMPLIANCE = "Compliance"
    COMMUNICATION = "Communication"
    INTEGRATION = "Integration"
    SCALABILITY = "Scalability"
    TRAINING = "Training"
    CULTURAL = "Cultural"
    INFRASTRUCTURE = "Infrastructure"
    ENVIRONMENTAL = "Environmental"
    POLITICAL = "Political"
    ECONOMIC = "Economic"
    HEALTHCARE = "Healthcare"
    EDUCATION = "Education"
    REGULATORY = "Regulatory"
    COMPETITION = "Competition"
    LABOR = "Labor"
    SUSTAINABILITY = "Sustainability"
    CUSTOMER_DEMAND = "Customer Demand"
    BEHAVIORAL = "Behavioral"
    EMOTIONAL = "Emotional"
    HEALTH = "Health"
    KNOWLEDGE = "Knowledge"
    ACCESSIBILITY = "Accessibility"
    FINANCIAL = "Financial"
    SOCIAL = "Social"
    WORKLOAD = "Workload"
    SKILL = "Skill"
    SATISFACTION = "Satisfaction"
    ADVANCEMENT = "Advancement"
    COMPENSATION = "Compensation"
    LEGAL = "Legal"
    ETHICAL = "Ethical"
    PRIVACY="Privacy"
    SECURITY="Security"
    OTHER="Other"
    
class Topic(BaseModel):
    name: str = Field(description="The specific topic that is causing the paint INSIDE THE QUOTE. Only use topics mentioned inside the quote.")
    topic_type: TopicType = Field(description="The category of Topic this falls into. Only use the topic types given. Choose other if there is no matching topic type.")
    match_space_topic:bool = Field(description="Is this the same topic or a subtopic of the given space.")
    match_quote_pain:bool =  Field(description="Is this topic causing pain inside the given quote.")
        
class Topic_Issue(BaseModel):
    name: str = Field(description="The specific issue with the topic that is causing the pain point. ONLY ONE TYPE OF ISSUE AT a time.")
    issue_type: IssueType =  Field(description="The type of issue with the topic. Only use the issue types given. Choose Other if there is no matching issue type.")
    description: str = Field(description="A short 1 sentence description of the specific issue the user mentioned.")
    
class PainPoint(BaseModel):
    chain_of_thought_pick_quote:str =Field(description="A chain of thought explaining step by step how this quote was chosen and how it clearly shows a pain point for this exact space. You must show that this quote mentions the exact space in a negative way in your reasoning. If you are unsure, say it it is not relevant. If you determine this is not a relevant quote that's ok, just don't hallucinate. Finish with a definitive conclusion whether this brings up a specific pain point with the given space.")
    quote: str = Field(description="A full quote clearly demonstrating the pain point. Always go for a longer quote that better demonstrates the pain point.")        
    is_quote_relevant:bool = Field(description="Is this a relevant quote? Determined by if it specifically mentions the space in a negative way.")
    issue_topic: Topic = Field(description="The specific topic that is causing the pain point inside the quote")
    issue: Topic_Issue = Field(description="The individual specific area of concern for this pain point. More specific issues are more valuable here. Specific processes or services unique to this space will be especially valued")
    issue_emotion:EmotionType  = Field(description="The type of emotion the user has towards the given issue topic. Only use the emotions given.  Choose other if there is no matching emotion.")
    description: str = Field(description="A description of the pain point.")
    title: str = Field(description="The title should ALWAYS start with a directional word  based on the the type of issue(Lack of, Diffuculty with, Seeking), the issue, and the topic. ")
    post_id: str = Field(description="The id of the post")
    persona: Optional[str] = Field(description="The persona this pain point falls in to. Enter null if it's unclear.")
    
class Persona(BaseModel):
    chain_of_thought_pick_persona: str = Field(
        description="A chain of thought explaining step by step how this persona was chosen, how it fits the exact perspective given and the space, how the quote directly shows the persona and how the persona. You must show that this persona directly matches the exact space and exact perspective and relates directly to the quote. If you are unsure, say it is not relevant. If you determine this is not a relevant persona or the quote is irrelevant that's ok, just don't hallucinate. Finish with a definitive conclusion whether this is a relevant specific persona that matches the quote. You must explicity conclude whether this persona is an exact match for the given perspective."
    )
    quote: str = Field(
        description="A representative quote that exemplifies this persona's perspective or typical statement"
    )
    is_quote_relevant: bool = Field(
        description="Is this a relevant quote and persona? Determined by if the persona is relevant to the space, matches the perspective and matches the quote."
    )
    title: str = Field(
        description="The title of the persona, e.g., 'The Newbie Lifter'"
    )
    post_id: str = Field(description="The id of the post")
    description: str = Field(
        description="A detailed description of the persona, including their characteristics, background, and typical behavior"
    )

class PersonaResponse(BaseModel):
    personas: Optional[List[Persona]] = Field(
        description="A list of personas, each representing a distinct user type or category"
    )
        
class PainPointsModel(BaseModel):
    pain_points: Optional[List[PainPoint]] = Field(None, description="A list of the extracted pain points from the Reddit posts.")

class ValidCluster(BaseModel):
    title: str = Field(..., description="Concise pain point title (3-7 words)")
    quote: str = Field(..., description="Representative quote showing the pain point with negative sentiment")
    quoteId: str = Field(..., description="ID of the representative quote")
    description: str = Field(..., description="Brief description of the common issue (1-4 sentences)")

class InvalidCluster(BaseModel):
    reason: str = Field(..., description="Brief explanation of why the cluster is invalid")

class ClusterAnalysis(BaseModel):
    validCluster: Optional[ValidCluster] = Field(None, description="Details of the valid cluster if the cluster is valid")
    invalidCluster: Optional[InvalidCluster] = Field(None, description="Details of the invalid cluster if the cluster is invalid")

class PainPointClusterItem(BaseModel):
    title: str = Field(description='Title of Pain Point')
    quote:str =  Field(description='Quote respresentative of Pain Point')
    description:str = Field(description="Description of the Pain Point")
    score:int  = Field(description="The score of the post/comment of the post.")
    time:str = Field(description="The time of quote")
    link:str = Field(description="The link to the quote")
    reddit_id: str = Field(description="The id of the post")
    persona:Optional[str] = Field(description="The assigned persona of the pain point")
        
class PainPointCluster(BaseModel):
    title: str = Field(description="Concise pain point title (3-7 words)")
    quote: str = Field(description="Representative quote showing the pain point with negative sentiment")
    score:int  = Field(description="The score of the post/comment of the post.")
    time:str = Field(description="The time of quote")
    link:str = Field(description="The link to the quote")
    description: str = Field(description="Brief description of the common issue (1-4 sentences)")
    percentage:float = Field(descripiton="The percentage of cluster items under this")
    sub_pain_points: List[PainPointClusterItem] = Field(description="A list of the sub pain points for this cluster")
    reddit_id: str = Field(description="The id of the post")

class ValidPersonaCluster(BaseModel):
    title: str = Field(..., description="Concise representative title (3-7 words)")
    quote: str = Field(..., description="Representative quote showing the persona")
    quoteId: str = Field(..., description="ID of the representative quote")
    description: str = Field(..., description="Brief description of the common persona (1-4 sentences)")

class InvalidPersonaCluster(BaseModel):
    reason: str = Field(..., description="Brief explanation of why the cluster is invalid")

class ClusterPersonaAnalysis(BaseModel):
    validCluster: Optional[ValidPersonaCluster] = Field(None, description="Details of the valid cluster if the cluster is valid")
    invalidCluster: Optional[InvalidPersonaCluster] = Field(None, description="Details of the invalid cluster if the cluster is invalid")
        
class PersonaClusterItem(BaseModel):
    title: str = Field(description='Title of Persona')
    quote:str =  Field(description='Quote respresentative of Persona')
    description:str = Field(description="Description of the Persona")
    score:Optional[int]  = Field(None,description="The score of the post/comment of the post.")
    time:Optional[str] = Field(None,description="The time of quote")
    link:str = Field(description="The link to the quote")
    reddit_id: str = Field(description="The id of the post")
        
class PersonaCluster(BaseModel):
    title: str = Field(description="Concise Persona title (3-7 words)")
    quote: str = Field(description="Representative quote showing the persona")
    score:Optional[int]  = Field(None,description="The score of the post/comment of the post.")
    time:Optional[str] = Field(None,description="The time of quote")
    link:str = Field(description="The link to the quote")
    description: str = Field(description="Brief description of the persona (1-4 sentences)")
    percentage:float = Field(descripiton="The percentage of cluster items under this")
    reddit_id: str = Field(description="The id of the post")
    sub_personas: List[PersonaClusterItem] = Field(description="A list of the sub personas for this cluster")
    top_pain_points: List[PainPointCluster] = Field(description="A list of the top pain points for this cluster")

class RedditPostAnalysis(BaseModel):
    space_match_reasoning:str = Field(description="Think step by step if this post truly matches the given space.")
    space_match: bool = Field(description="Whether the post is relevant to the given space")
    perspective_match_reasoning:str = Field(description="Think step by step if this post's author is the given perspective .")
    perspective_match: bool = Field(description="Whether the user writing this post is the given perspective.")

class QueryList(BaseModel):
    query: List[str] = Field(description="List of alternate queries")

class HydeResp(BaseModel):
    hyde: str = Field(description="A hypothetical post that answers the query.")