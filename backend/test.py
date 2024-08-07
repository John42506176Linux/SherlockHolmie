import weaviate
import os
import logging.handlers
from dotenv import load_dotenv
from managers.databaseManager import DatabaseManager

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()
# Set these environment variables
URL = os.getenv("WCS_URL")
APIKEY = os.getenv("WCS_API_KEY")
  
# Connect to a WCS instance
client = weaviate.connect_to_wcs(
    cluster_url=URL,
    auth_credentials=weaviate.auth.AuthApiKey(APIKEY))