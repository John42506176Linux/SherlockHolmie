import weaviate
import os
import logging
import logging.handlers
from dotenv import load_dotenv
from managers.databaseManager import DatabaseManager
import weaviate.classes as wvc
import requests
import json

# Set up logging
log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

# Create a file handler
file_handler = logging.handlers.RotatingFileHandler(
    "bot.log", maxBytes=10485760, backupCount=5)
file_handler.setLevel(logging.DEBUG)

# Create a console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create a formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
log.addHandler(file_handler)
log.addHandler(console_handler)

log.info("Starting the Weaviate data import script")

load_dotenv()
# Set these environment variables
URL = os.getenv("WCS_URL")
APIKEY = os.getenv("WCS_API_KEY")

log.debug(f"WCS_URL: {URL}")
log.debug(f"WCS_API_KEY: {'*' * len(APIKEY)}")  # Mask the API key in logs

# Connect to a WCS instance
log.info("Connecting to WCS instance")
try:
    client = weaviate.connect_to_wcs(
        cluster_url=URL,
        auth_credentials=weaviate.auth.AuthApiKey(APIKEY))
    log.info("Successfully connected to WCS instance")
except Exception as e:
    log.error(f"Failed to connect to WCS instance: {str(e)}")
    raise

fname = "jeopardy_tiny_with_vectors_all-OpenAI-ada-002.json"
url = f"https://raw.githubusercontent.com/weaviate-tutorials/quickstart/main/data/{fname}"
log.info(f"Fetching data from {url}")

try:
    resp = requests.get(url)
    resp.raise_for_status()
    data = json.loads(resp.text)
    log.info(f"Successfully fetched and parsed data. Total items: {len(data)}")
except requests.RequestException as e:
    log.error(f"Failed to fetch data: {str(e)}")
    raise
except json.JSONDecodeError as e:
    log.error(f"Failed to parse JSON data: {str(e)}")
    raise

question_objs = list()
log.info("Processing data and creating DataObjects")
for i, d in enumerate(data):
    question_objs.append(wvc.data.DataObject(
        properties={
            "answer": d["Answer"],
            "question": d["Question"],
            "category": d["Category"],
        },
        vector=d["vector"]
    ))
    if (i + 1) % 100 == 0:
        log.debug(f"Processed {i + 1} items")

log.info(f"Created {len(question_objs)} DataObjects")

questions = client.collections.get("Question")
log.info("Inserting data into Weaviate")
try:
    questions.data.insert_many(question_objs)
    log.info("Successfully inserted all data into Weaviate")
except Exception as e:
    log.error(f"Failed to insert data into Weaviate: {str(e)}")
    raise

log.info("Closing Weaviate client connection")
client.close()

log.info("Script execution completed successfully")