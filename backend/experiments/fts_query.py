import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

import logging.handlers
from dotenv import load_dotenv
import time
from managers.databaseManager import DatabaseManager

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()

db_manager = DatabaseManager()
log.info("Database Manager created")
start_time = time.time()
rows = db_manager.space_search_query("CryptoCurrency",fast=True,threshold=0.55)
log.info("Elapsed time: %s", time.time() - start_time)
log.info("Rows: %s", rows)


