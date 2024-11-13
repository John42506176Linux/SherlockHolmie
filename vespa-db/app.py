from vespa.application import Vespa
from vespa.io import VespaResponse, VespaQueryResponse
import time
import asyncio
import json
import json
import subprocess

app = Vespa(url = "http://localhost:8080")

from dataclasses import dataclass
from typing import Callable, Optional, Iterable, Dict


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
documents = [
    {
        "reddit_id": "t3_xyz345",
        "link_id": "t3_xyz345",
        "subreddit_name": "space",
        "title": "James Webb Space Telescope captures stunning image of Jupiter's Great Red Spot",
        "author": "space_geek",
        "created_utc": 1706224000,
        "url": "https://www.reddit.com/r/space/comments/xyz345/james_webb_space_telescope_captures_stunning_image_of_jupiters_great_red_spot/",
        "body": "The James Webb Space Telescope has captured its first detailed image of Jupiter, revealing the giant planet's swirling atmosphere and the Great Red Spot in unprecedented detail. What do you think this discovery tells us about Jupiter's weather patterns?",
        "score": 1800,
        "num_comments": 278,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["James Webb Space Telescope", "Jupiter", "Great Red Spot", "space exploration", "astronomy"]
    },
    {
        "reddit_id": "t3_mno987",
        "link_id": "t3_mno987",
        "subreddit_name": "programming",
        "title": "Python vs. JavaScript: Choosing the right language for your next project",
        "author": "code_whisperer",
        "created_utc": 1715916800,
        "url": "https://www.reddit.com/r/programming/comments/mno987/python_vs_javascript_choosing_the_right_language_for_your_next_project/",
        "body": "Both Python and JavaScript are popular programming languages, but they excel in different areas. When would you choose Python and when would you choose JavaScript? Let's discuss the pros and cons of each for different project types.",
        "score": 1200,
        "num_comments": 512,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["Python", "JavaScript", "programming languages", "web development", "data science"]
    },
    {
        "reddit_id": "t3_abc123",
        "link_id": "t3_abc123",
        "subreddit_name": "ArtificialIntelligence",
        "title": "The ethics of AI: Balancing progress and responsibility",
        "author": "ai_ethicist",
        "created_utc": 1725609600,
        "url": "https://www.reddit.com/r/ArtificialIntelligence/comments/abc123/the_ethics_of_ai_balancing_progress_and_responsibility/",
        "body": "As AI continues to advance rapidly, we need to consider the ethical implications of these technologies. How can we ensure that AI development remains responsible and beneficial to society?",
        "score": 2200,
        "num_comments": 456,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["AI ethics", "artificial intelligence", "technology ethics", "responsible AI", "societal impact"]
    },
    {
        "reddit_id": "t3_def456",
        "link_id": "t3_def456",
        "subreddit_name": "datascience",
        "title": "The rise of AutoML: Will it replace data scientists?",
        "author": "ml_enthusiast",
        "created_utc": 1735302400,
        "url": "https://www.reddit.com/r/datascience/comments/def456/the_rise_of_automl_will_it_replace_data_scientists/",
        "body": "AutoML tools are becoming increasingly sophisticated. Do you think these tools will eventually replace human data scientists, or will they simply augment their capabilities?",
        "score": 980,
        "num_comments": 324,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["AutoML", "data science", "machine learning", "AI tools", "job market"]
    },
    {
        "reddit_id": "t3_ghi789",
        "link_id": "t3_ghi789",
        "subreddit_name": "cybersecurity",
        "title": "The future of quantum cryptography: Are we prepared?",
        "author": "quantum_sec",
        "created_utc": 1744995200,
        "url": "https://www.reddit.com/r/cybersecurity/comments/ghi789/the_future_of_quantum_cryptography_are_we_prepared/",
        "body": "With the advancement of quantum computing, traditional encryption methods may become obsolete. How can we prepare for the era of quantum cryptography?",
        "score": 1500,
        "num_comments": 287,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["quantum cryptography", "cybersecurity", "encryption", "quantum computing", "information security"]
    },
    {
        "reddit_id": "t3_jkl012",
        "link_id": "t3_jkl012",
        "subreddit_name": "MachineLearning",
        "title": "Transformer models: Beyond NLP applications",
        "author": "ml_researcher",
        "created_utc": 1754688000,
        "url": "https://www.reddit.com/r/MachineLearning/comments/jkl012/transformer_models_beyond_nlp_applications/",
        "body": "Transformer models have revolutionized NLP, but their potential extends beyond language tasks. What are some innovative applications of transformers in other domains?",
        "score": 2800,
        "num_comments": 423,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["transformer models", "machine learning", "NLP", "AI applications", "deep learning"]
    },
    {
        "reddit_id": "t3_mno345",
        "link_id": "t3_mno345",
        "subreddit_name": "technology",
        "title": "The environmental impact of cryptocurrency mining: Can it be sustainable?",
        "author": "eco_tech",
        "created_utc": 1764380800,
        "url": "https://www.reddit.com/r/technology/comments/mno345/the_environmental_impact_of_cryptocurrency_mining_can_it_be_sustainable/",
        "body": "Cryptocurrency mining consumes vast amounts of energy. Are there ways to make this process more environmentally friendly, or should we be looking at alternative technologies?",
        "score": 3200,
        "num_comments": 789,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["cryptocurrency", "environmental impact", "sustainable technology", "blockchain", "energy consumption"]
    },
    {
        "reddit_id": "t3_pqr678",
        "link_id": "t3_pqr678",
        "subreddit_name": "Futurology",
        "title": "Brain-computer interfaces: The next frontier in human-machine interaction",
        "author": "neurotech_fan",
        "created_utc": 1774073600,
        "url": "https://www.reddit.com/r/Futurology/comments/pqr678/brain_computer_interfaces_the_next_frontier_in_human_machine_interaction/",
        "body": "Brain-computer interfaces are advancing rapidly. How might these technologies change the way we interact with computers and each other in the future?",
        "score": 4100,
        "num_comments": 567,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["brain-computer interface", "neurotechnology", "human-machine interaction", "future tech", "cognitive science"]
    },
    {
        "reddit_id": "t3_stu901",
        "link_id": "t3_stu901",
        "subreddit_name": "robotics",
        "title": "Soft robotics: Revolutionizing human-robot interaction",
        "author": "robo_engineer",
        "created_utc": 1783766400,
        "url": "https://www.reddit.com/r/robotics/comments/stu901/soft_robotics_revolutionizing_human_robot_interaction/",
        "body": "Soft robotics is emerging as a game-changer in human-robot interaction. What are some potential applications and challenges in this field?",
        "score": 1700,
        "num_comments": 298,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["soft robotics", "human-robot interaction", "biomimicry", "robotics engineering", "material science"]
    },
    {
        "reddit_id": "t3_vwx234",
        "link_id": "t3_vwx234",
        "subreddit_name": "Physics",
        "title": "Dark matter: New theories and detection methods",
        "author": "cosmology_buff",
        "created_utc": 1793459200,
        "url": "https://www.reddit.com/r/Physics/comments/vwx234/dark_matter_new_theories_and_detection_methods/",
        "body": "Recent advancements in physics have led to new theories about dark matter. What are some promising approaches to detecting and understanding this elusive substance?",
        "score": 2600,
        "num_comments": 412,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["dark matter", "astrophysics", "particle physics", "cosmology", "scientific theories"]
    },
    {
        "reddit_id": "t3_yz5678",
        "link_id": "t3_yz5678",
        "subreddit_name": "compsci",
        "title": "Quantum computing: Practical applications on the horizon",
        "author": "quantum_dev",
        "created_utc": 1803152000,
        "url": "https://www.reddit.com/r/compsci/comments/yz5678/quantum_computing_practical_applications_on_the_horizon/",
        "body": "As quantum computers become more powerful, what practical applications do you see emerging in the near future? How might this technology impact various industries?",
        "score": 1900,
        "num_comments": 345,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["quantum computing", "computer science", "emerging technology", "industry applications", "computational power"]
    },
    {
        "reddit_id": "t3_bcd901",
        "link_id": "t3_bcd901",
        "subreddit_name": "biotech",
        "title": "CRISPR advancements: Ethical considerations in gene editing",
        "author": "gene_therapist",
        "created_utc": 1812844800,
        "url": "https://www.reddit.com/r/biotech/comments/bcd901/crispr_advancements_ethical_considerations_in_gene_editing/",
        "body": "CRISPR technology is advancing rapidly, opening up new possibilities in gene editing. What are the ethical implications of these advancements, and how should we approach regulation?",
        "score": 2300,
        "num_comments": 501,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["CRISPR", "gene editing", "bioethics", "biotechnology", "genetic engineering"]
    },
    {
        "reddit_id": "t3_efg234",
        "link_id": "t3_efg234",
        "subreddit_name": "netsec",
        "title": "Zero-trust architecture: The future of network security?",
        "author": "security_architect",
        "created_utc": 1822537600,
        "url": "https://www.reddit.com/r/netsec/comments/efg234/zero_trust_architecture_the_future_of_network_security/",
        "body": "Zero-trust architecture is gaining traction in cybersecurity. What are the benefits and challenges of implementing this approach in modern networks?",
        "score": 1600,
        "num_comments": 287,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["zero-trust architecture", "network security", "cybersecurity", "IT infrastructure", "data protection"]
    },
    {
        "reddit_id": "t3_hij567",
        "link_id": "t3_hij567",
        "subreddit_name": "MachineLearning",
        "title": "Federated Learning: Balancing privacy and model performance",
        "author": "privacy_ml_expert",
        "created_utc": 1832230400,
        "url": "https://www.reddit.com/r/MachineLearning/comments/hij567/federated_learning_balancing_privacy_and_model_performance/",
        "body": "Federated Learning allows for training models on distributed data without compromising privacy. What are the trade-offs between model performance and data privacy in this approach?",
        "score": 2100,
        "num_comments": 378,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["Federated Learning", "machine learning", "data privacy", "distributed computing", "AI ethics"]
    },
    {
        "reddit_id": "t3_klm890",
        "link_id": "t3_klm890",
        "subreddit_name": "space",
        "title": "Mars colonization: Overcoming technological and biological challenges",
        "author": "mars_explorer",
        "created_utc": 1841923200,
        "url": "https://www.reddit.com/r/space/comments/klm890/mars_colonization_overcoming_technological_and_biological_challenges/",
        "body": "As we get closer to potential Mars missions, what are the biggest technological and biological challenges we need to overcome for long-term colonization?",
        "score": 3800,
        "num_comments": 642,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["Mars colonization", "space exploration", "astrobiology", "space technology", "human spaceflight"]
    },
    {
        "reddit_id": "t3_nop123",
        "link_id": "t3_nop123",
        "subreddit_name": "programming",
        "title": "The rise of low-code and no-code platforms: Threat or opportunity for developers?",
        "author": "code_simplifier",
        "created_utc": 1851616000,
        "url": "https://www.reddit.com/r/programming/comments/nop123/the_rise_of_low_code_and_no_code_platforms_threat_or_opportunity_for_developers/",
        "body": "Low-code and no-code platforms are becoming increasingly popular. How do you think this trend will impact the role of traditional software developers?",
        "score": 1400,
        "num_comments": 523,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["low-code", "no-code", "software development", "programming trends", "developer roles"]
    },
    {
        "reddit_id": "t3_qrs456",
        "link_id": "t3_qrs456",
        "subreddit_name": "datascience",
        "title": "Explainable AI: Making black-box models transparent",
        "author": "ai_interpreter",
        "created_utc": 1861308800,
        "url": "https://www.reddit.com/r/datascience/comments/qrs456/explainable_ai_making_black_box_models_transparent/",
        "body": "Explainable AI is crucial for building trust in AI systems. What are some effective techniques for making complex models more interpretable?",
        "score": 1800,
        "num_comments": 312,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["Explainable AI", "interpretable machine learning", "AI transparency", "data science", "model interpretation"]
    },
    {
        "reddit_id": "t3_tuv789",
        "link_id": "t3_tuv789",
        "subreddit_name": "Futurology",
        "title": "Transhumanism: The ethics of human enhancement technologies",
        "author": "future_human",
        "created_utc": 1871001600,
        "url": "https://www.reddit.com/r/Futurology/comments/tuv789/transhumanism_the_ethics_of_human_enhancement_technologies/",
        "body": "As human enhancement technologies advance, we face complex ethical questions. How should we approach the development and regulation of these technologies?",
        "score": 2700,
        "num_comments": 589,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["transhumanism", "human enhancement", "bioethics", "future technology", "technological ethics"]
    },
    {
        "reddit_id": "t3_wxy012",
        "link_id": "t3_wxy012",
        "subreddit_name": "Physics",
        "title": "Quantum entanglement: Recent breakthroughs and future applications",
        "author": "quantum_physicist",
        "created_utc": 1880694400,
        "url": "https://www.reddit.com/r/Physics/comments/wxy012/quantum_entanglement_recent_breakthroughs_and_future_applications/",
        "body": "Recent experiments have pushed the boundaries of quantum entanglement. What are some potential real-world applications of this phenomenon?",
        "score": 2200,
        "num_comments": 401,
        "is_post": True,
        "parent_post": "",
        "archived": False,
        "keywords": ["quantum entanglement", "quantum physics", "scientific breakthroughs", "quantum technology", "physics applications"]
    }
]


def callback(response: VespaResponse, id: str):
    if not response.is_successful():
        print(f"Error when feeding document {id}: {response.get_json()}")

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

def json_to_file(name,documents):
    # Create the JSONL file
    with open(name, 'w') as f:
        for doc in documents:
            jsonl_line = doc_to_jsonl(doc)
            f.write(jsonl_line + '\n')

def feed_to_vespa(file_name):
    command = f"vespa feed --target http://192.168.200.1:8080 {file_name}"
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Successfully fed {file_name} to Vespa.")
    except subprocess.CalledProcessError as e:
        print(f"Error feeding {file_name} to Vespa: {e}")


async def feed_async(params: FeedParams, data: Iterable[Dict]) -> FeedResult:
    start_time = time.time()
    tasks = []
    # We use a semaphore to limit the number of concurrent requests, this is useful to avoid
    # running into memory issues when feeding a large number of documents
    semaphore = asyncio.Semaphore(params.num_concurrent_requests)

    async with app.asyncio(
        connections=params.max_connections,
        total_timeout=10000
    ) as async_app:
        for doc in data:
            print("KeyWord: ", doc["keywords"])
            async with semaphore:
                task = asyncio.create_task(
                    async_app.feed_data_point(
                        data_id=doc["reddit_id"],
                        fields={
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
                            "keywords": doc["keywords"],
                            "url": doc["url"],
                        },
                        namespace="pyvespa-feed",
                        schema="reddit_post",
                    )
                )
                tasks.append(task)

        await asyncio.wait(tasks, return_when=asyncio.ALL_COMPLETED)

    end_time = time.time()
    return FeedResult(
        **params.__dict__,
        feed_time=end_time - start_time,
    )

async def main():
    params = FeedParams(
        name="reddit_post",
        num_docs=len(documents),
        max_connections=20,
        function_name="feed_async",
        num_concurrent_requests=20
    )
    result = await feed_async(params=params, data=documents)
    print(f"Fed {result.num_docs} documents in {result.feed_time:.2f} seconds")

if __name__ == "__main__":
    # asyncio.run(main())
    print("Starting Json Process:")
    start_time = time.time()
    json_to_file(f"vespa_feed-{len(documents)}.jsonl", documents)
    print(f"Elapsed Json Time: {time.time() - start_time:.2f} seconds")
    start_time = time.time()
    feed_to_vespa(f"vespa_feed-{len(documents)}.jsonl")
    end_time = time.time()
    print(f"Elapsed Time: {time.time() - start_time:.2f} seconds")

