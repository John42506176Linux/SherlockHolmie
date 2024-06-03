from fastapi import FastAPI, HTTPException
import logging.handlers
from dotenv import load_dotenv
import time
from managers.databaseManager import DatabaseManager
from managers.reportManager import ReportManager

app = FastAPI()

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

load_dotenv()


@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/process_space")
async def process_space(space: str, fast: bool = True, threshold: float = 0.55):
    start_time = time.time()
    report_manager = ReportManager(DatabaseManager())
    log.info("Database Manager created")
    try:
        # Initialize space
        log.info(f"Initializing Space:{space}")
        report_manager.initialize_space(space,fast=fast,threshold=threshold)
        log.info(f"Space Size:{report_manager.get_space_size()}")

        # Get pain points
        pain_points = report_manager.get_pain_points(batch_size=50)
        # Get personas
        personas = report_manager.get_personas(quantify=True)

        return {
            "Initialization Time": time.time() - start_time,
            "Pain Points": pain_points,
            "Personas": personas
        }
    except Exception as e:
        log.error(f"Error processing space:{e}")
        raise HTTPException(status_code=400, detail=str(e))
    

@app.post("/process_query")
async def process_query(query: str, space:str,fast: bool = True, threshold: float = 0.55):
    start_time = time.time()
    report_manager = ReportManager(DatabaseManager())
    log.info("Database Manager created")
    try:
        # Initialize space
        log.info(f"Initializing Space:{query}")
        report_manager.initialize_query(query=query,space=space,fast=fast,threshold=threshold)
        log.info(f"Space Size:{report_manager.get_query_size()}")

        # Get insights
        insights = report_manager.get_insights()

        return {
            "Initialization Time": time.time() - start_time,
            "Insights": insights
        }
    except Exception as e:
        log.error(f"Error processing space:{e}")
        raise HTTPException(status_code=400, detail=str(e))