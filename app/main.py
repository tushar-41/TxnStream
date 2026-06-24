from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import jobs

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Alemeno Transaction Pipeline",
    description=(
        "Backend APIs for uploading transaction CSV files, polling queued jobs, "
        "and retrieving cleaned transaction results, anomalies, and summaries. "
        "Use the interactive Swagger UI at /docs."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    openapi_tags=[
        {
            "name": "jobs",
            "description": "Upload CSV files, poll background jobs, and fetch processed results.",
        }
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://txnstream.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])

@app.get("/")
def root():
    return {
        "message": "Alemeno Transaction Pipeline is running",
        "swagger": "/docs",
        "openapi": "/openapi.json",
    }
