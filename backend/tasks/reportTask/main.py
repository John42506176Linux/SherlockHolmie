from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from celery.result import AsyncResult
from managers.celeryManager import process_space_task,app as celery_app
from request_params.space_params import SpaceParams

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


@app.get("/")
async def health_check():
    return {"status": "Everything is fine"}

@app.post("/process_space")
async def process_space(params: SpaceParams):
    task_id = process_space_task.delay(params.dict())
    print(f"Hi I'm here:{task_id}")
    return {"status": "Report generation has started. Please wait...","success":True} 

@app.get("/task_status/{task_id}")
async def get_task_status(task_id: str):
    task_result = AsyncResult(task_id, app=celery_app)
    if task_result.state == 'PENDING':
        response =  {
            "state": task_result.state,
            "status": "Task is pending..."
        }
    elif task_result.state != 'FAILURE':
        response = {
            "state": task_result.state,
            "status": task_result.info,
        }
    else:
        response = {
            "state": task_result.state,
            "status": str(task_result.info),  # this is the exception raised
        }
    return response