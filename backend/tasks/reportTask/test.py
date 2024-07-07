from fastapi import FastAPI, HTTPException, BackgroundTasks
import logging
from dotenv import load_dotenv
import time
from managers.databaseManager import DatabaseManager
from managers.reportManager import ReportManager
from managers.reportDatabaseManager import ReportDatabaseManager
from fastapi.middleware.cors import CORSMiddleware
from request_params.space_params import SpaceParams
from request_params.insight_params import InsightParams
from request_params.report_params import ReportParams

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

def process_space_task(params: SpaceParams):
    start_time = time.time()
    report_manager = ReportManager(DatabaseManager())
    log.info("Database Manager created")
    try:
        # Initialize space
        log.info(f"Initializing Space: {params.space}")
        report_manager.initialize_space(params.space, fast=params.fast, threshold=params.threshold, perspective=params.perspective, context=params.context)
        log.info(f"Space Size: {report_manager.get_space_size()}")

        # Get pain points
        pain_points = report_manager.get_pain_points(batch_size=params.batch_size,concurrency=params.concurrency)
        # Get personas
        personas = report_manager.get_personas(quantify=True)

        log.info("Task completed")
        log.info({
            "Initialization Time": time.time() - start_time,
            "Pain Points": pain_points,
            "Personas": personas
        })
    except Exception as e:
        log.error(f"Error processing space: {e}")

@app.post('/start_report')
async def start_report(params: ReportParams, background_tasks: BackgroundTasks):
    report_manager = ReportDatabaseManager()
    report_manager.initialize_database()
    report_id = report_manager.insert_report(params.space, params.name, params.email)
    if report_id is None:
        raise HTTPException(status_code=500, detail="Error inserting report")
    else:
        background_tasks.add_task(process_space_task, SpaceParams(space=params.space, perspective=params.perspective, context=params.context, fast=params.fast, threshold=params.threshold, batch_size=params.batch_size))
        return {"message": "Report processing started","report_id": report_id}
    
@app.post("/process_space")
async def process_space(params: SpaceParams, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_space_task, params)
    return {"message": "Space processing started"}

def process_query_task(params: InsightParams):
    start_time = time.time()
    report_manager = ReportManager(DatabaseManager())
    log.info("Database Manager created")
    try:
        # Initialize space
        log.info(f"Initializing Space: {params.query}")
        report_manager.initialize_query(query=params.query, space=params.space, fast=params.fast, threshold=params.threshold, perspective=params.perspective, context=params.context)
        log.info(f"Space Size: {report_manager.get_query_size()}")

        # Get insights
        insights = report_manager.get_insights(batch_size=params.batch_size)

        log.info("Task completed")
        log.info({
            "Initialization Time": time.time() - start_time,
            "query": params.query,
            "Insights": insights
        })
    except Exception as e:
        log.error(f"Error processing query: {e}")

@app.post("/process_insights")
async def process_query(params: InsightParams, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_query_task, params)
    return {"message": "Query processing started"}
