from celery import Celery
import logging
import time
from managers.databaseManager import DatabaseManager
from managers.weaviateDBManager import WeaviateManager

from managers.reportManager import ReportManager
import os 
import requests

NEXTJS_API_URL=os.getenv('NEXTJS_API_URL')
REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379/0')

app = Celery(
    'reportTask',
    broker=REDIS_URL,
    backend=REDIS_URL
)
log = logging.getLogger("bot")

@app.task
def process_space_task(params):
    wv_manager = WeaviateManager()
    start_time = time.time()
    report_manager = ReportManager(wv_manager)
    log.info("Database Manager created")
    try:
        log.info(f"Initializing Space: {params['space']}")
        report_manager.initialize_space(
            params['space'],
            fast=False,
            threshold=params['threshold'],
            perspective=params['perspective'],
            perspective_specific=params['perspective_specific'],
            context=params['context']
        )
        log.info(f"Space Size: {report_manager.get_space_size()}")

        report_manager.get_personas(
            concurrency=params['concurrency'],
            batch_size=params['batch_size']
        )

        report_manager.get_pain_points(
            concurrency=params['concurrency'],
            batch_size=params['batch_size']
        )
        pain_points_dict = [pp.dict() for pp in report_manager.pain_points]
        personas_dict = [p.dict() for p in report_manager.personas]

        result = {
            "Pain Points": pain_points_dict,
            "Personas": personas_dict,
            "Ids": [report_manager.ids]
        }

        # Send result to Next.js API
        requests.post(NEXTJS_API_URL, json={"requestId": params['request_id'], "result": result})
        return result
    except Exception as e:
        log.error(f"Error processing space: {e}")
        return {"error": str(e)}
    finally:
        wv_manager.close()