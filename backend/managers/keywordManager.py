from keybert import KeyBERT
from keyphrase_vectorizers import KeyphraseCountVectorizer
from managers.embeddedManager import CustomEmbedder
import os
import logging



log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)


class KeywordManager():
    def __init__(self):
        self.custom_embedder = CustomEmbedder(model_name=os.getenv('AWS_EMBEDDING_MODEL'))
        self.custom_kw_model = KeyBERT(model=self.custom_embedder)
        self.vectorizer = KeyphraseCountVectorizer()

    def get_keywords(self, documents,doc_embeddings=None,word_embeddings=None):
        try:
            log.info("Extracting keywords")
            keywords = self.custom_kw_model.extract_keywords(documents,doc_embeddings=doc_embeddings,word_embeddings=word_embeddings, vectorizer=self.vectorizer,use_mmr=True,diversity=0.5)
            self.keywords = keywords
            return keywords
        except Exception as e:
            log.error(f"Error extracting keywords: {e}")
            return []

    def embed_keywords(self):
        keyword_strs = []
        for kw in self.keywords:
            keyword_strs.append(', '.join([item[0] for item in kw]))
        return self.custom_embedder.embed(keyword_strs)
