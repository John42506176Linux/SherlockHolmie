from fastapi import FastAPI, HTTPException
import logging.handlers
from dotenv import load_dotenv
import time
from managers.databaseManager import DatabaseManager
from managers.reportManager import ReportManager
from fastapi.middleware.cors import CORSMiddleware
from request_params.space_params import SpaceParams
from request_params.insight_params import InsightParams

app = FastAPI()

log = logging.getLogger("bot")
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler())

origins = [
    "http://localhost:3000",  # Replace with your actual origin
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
   
)

load_dotenv()


@app.get("/")
async def health_check():
    return {"status": "ok"}

@app.post("/process_space")
async def process_space(params: SpaceParams):
    start_time = time.time()
    report_manager = ReportManager(DatabaseManager())
    log.info("Database Manager created")
    try:
        # Initialize space
        log.info(f"Initializing Space:{params.space}")
        report_manager.initialize_space(params.space,fast=params.fast,threshold=params.threshold)
        log.info(f"Space Size:{report_manager.get_space_size()}")

        # Get pain points
        pain_points = report_manager.get_pain_points(batch_size=params.batch_size)
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


@app.post("/process_insights")
async def process_query(params: InsightParams):
    start_time = time.time()
    report_manager = ReportManager(DatabaseManager())
    log.info("Database Manager created")
    try:
        # Initialize space
        log.info(f"Initializing Space:{params.query}")
        report_manager.initialize_query(query=params.query,space=params.space,fast=params.fast,threshold=params.threshold)
        log.info(f"Space Size:{report_manager.get_query_size()}")

        # Get insights
        insights = report_manager.get_insights(batch_size=params.batch_size)

        return {
            "Initialization Time": time.time() - start_time,
            "query": params.query,
            "Insights": insights
        }
    except Exception as e:
        log.error(f"Error processing space:{e}")
        raise HTTPException(status_code=400, detail=str(e))