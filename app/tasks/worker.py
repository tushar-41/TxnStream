from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "worker",
    broker=os.getenv("REDIS_URL"),
    backend=os.getenv("REDIS_URL"),
)

celery_app.conf.update(
    task_default_queue="main-queue",
    task_routes={
        "app.tasks.pipeline.process_job": {"queue": "main-queue"},
    },
)

import app.tasks.pipeline
