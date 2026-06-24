import io

import pandas as pd
from fastapi import APIRouter, Depends, UploadFile, File, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.models import Job, Transaction, JobSummary
from app.schemas import JobResponse, JobStatusResponse, JobResultsResponse, JobListItem, TransactionOut
from app.tasks.cleaner import REQUIRED_COLUMNS
from app.tasks.pipeline import process_job

router = APIRouter()


@router.post("/upload", response_model=JobResponse)
async def upload_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only standard CSV files are accepted.")

    try:
        contents = await file.read()
        csv_content = contents.decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid text encoding detected within the file.")

    try:
        header_df = pd.read_csv(io.StringIO(csv_content), nrows=0)
    except Exception:
        raise HTTPException(status_code=400, detail="Uploaded file could not be parsed as CSV.")

    missing = REQUIRED_COLUMNS - set(header_df.columns)
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV is missing required columns: {', '.join(sorted(missing))}"
        )

    # Instantiate a job tracking record
    new_job = Job(filename=file.filename, status="pending")
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Dispatches asynchronously to worker via message broker
    process_job.delay(new_job.id, csv_content)

    return JobResponse(
        job_id=new_job.id,
        status=new_job.status,
        message="Transaction processing job safely queued up."
    )


@router.get("/{job_id}/status", response_model=JobStatusResponse)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Requested job execution context not found.")

    summary_dict = None
    if job.status == "completed" and job.summary:
        summary_dict = {
            "total_spend_inr": job.summary.total_spend_inr,
            "total_spend_usd": job.summary.total_spend_usd,
            "top_merchants": job.summary.top_merchants,
            "anomaly_count": job.summary.anomaly_count,
            "narrative": job.summary.narrative,
            "risk_level": job.summary.risk_level
        }

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        filename=job.filename,
        row_count_raw=job.row_count_raw,
        row_count_clean=job.row_count_clean,
        created_at=job.created_at,
        completed_at=job.completed_at,
        error_message=job.error_message,
        summary=summary_dict
    )


@router.get("/{job_id}/results", response_model=JobResultsResponse)
def get_job_results(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job entry not found.")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail=f"Job results cannot be viewed while status is: {job.status}")

    transactions = db.query(Transaction).filter(Transaction.job_id == job_id).all()
    anomalies = [t for t in transactions if t.is_anomaly]

    # Calculate category breakdowns dynamically for the complete report representation
    breakdown = {}
    for t in transactions:
        cat = t.llm_category if (t.category == "Uncategorised" and t.llm_category) else t.category
        breakdown[cat] = breakdown.get(cat, 0.0) + (t.amount or 0.0)

    summary_dict = {
        "total_spend_inr": job.summary.total_spend_inr,
        "total_spend_usd": job.summary.total_spend_usd,
        "top_merchants": job.summary.top_merchants,
        "anomaly_count": job.summary.anomaly_count,
        "narrative": job.summary.narrative,
        "risk_level": job.summary.risk_level
    }

    return JobResultsResponse(
        job_id=job.id,
        transactions=transactions,
        anomalies=anomalies,
        category_breakdown=breakdown,
        summary=summary_dict
    )


@router.get("", response_model=List[JobListItem])
def list_all_jobs(status: Optional[str] = Query(None), db: Session = Depends(get_db)):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status.lower())

    jobs = query.order_by(Job.created_at.desc()).all()
    return [
        JobListItem(
            job_id=j.id,
            status=j.status,
            filename=j.filename,
            row_count_raw=j.row_count_raw,
            created_at=j.created_at
        ) for j in jobs
    ]
