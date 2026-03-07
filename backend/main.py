from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from dotenv import load_dotenv

import database
from scheduler import start_scheduler, update_job_interval, shutdown_scheduler

load_dotenv()

app = FastAPI(title="Dfacto Crawler API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    start_scheduler()

@app.on_event("shutdown")
def on_shutdown():
    shutdown_scheduler()

class ConfigUpdate(BaseModel):
    keywords: str
    timer_interval: int

class Headline(BaseModel):
    id: int
    title: str
    source: str
    url: str
    snippet: str
    verdict: str
    confidence_score: float
    explanation: str
    timestamp: str

@app.get("/config")
def get_config():
    return database.get_config()

@app.post("/config")
def update_config(config: ConfigUpdate):
    if config.timer_interval < 1:
        raise HTTPException(status_code=400, detail="Timer interval must be at least 1 minute.")
    
    database.update_config(config.keywords, config.timer_interval)
    update_job_interval(config.timer_interval)
    return {"message": "Configuration updated successfully", "config": config.model_dump()}

@app.get("/headlines")
def get_headlines(limit: int = 50):
    return database.get_headlines(limit=limit)
    
@app.post("/trigger")
def trigger_crawler_now(background_tasks: BackgroundTasks):
    from scheduler import fetch_and_store_headlines
    background_tasks.add_task(fetch_and_store_headlines)
    return {"message": "Crawler triggered. Generating headlines in background..."}
