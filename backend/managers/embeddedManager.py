from keybert.backend import BaseEmbedder
import requests
import os
from tqdm import tqdm
import numpy as np
from keybert import KeyBERT
from keyphrase_vectorizers import KeyphraseCountVectorizer
import weaviate
import os
import logging
import weaviate.classes as wvc
from weaviate.util import generate_uuid5
import datetime
from datetime import datetime, timezone
from utilities.utils import embed_documents
from tenacity import retry, stop_after_attempt
import time
from weaviate.classes.init import AdditionalConfig, Timeout
from weaviate.config import ConnectionConfig


log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)

class CustomEmbedder(BaseEmbedder):
    def __init__(self, model_name,dimensions=512):
        super().__init__()
        self.model_name = model_name
        self.dimensions = dimensions

    def embed(self, documents, verbose=False):
        embeddings = embed_documents(self.model_name,documents,dimensions=self.dimensions)
        return embeddings

   


