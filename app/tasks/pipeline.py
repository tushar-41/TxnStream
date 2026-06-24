import io
from datetime import datetime
import pandas as pd
from sqlalchemy.orm import Session

from app.tasks.worker import celery_app
from app.database import SessionLocal
from app.models import Job, Transaction, JobSummary
from app.tasks.cleaner import clean_dataframe
from app.tasks.anomaly import detect_anomalies
from app.tasks.llm import classify_transactions, generate_narrative_summary


@celery_app.task(name="app.tasks.pipeline.process_job")
def process_job(job_id: str, csv_content: str):
    db: Session = SessionLocal()
    job = db.query(Job).filter(Job.id == job_id).first()

    if not job:
        db.close()
        return f"Job {job_id} not found."

    try:
        job.status = "processing"
        db.commit()

        # Load CSV data into a Pandas DataFrame
        df_raw = pd.read_csv(io.StringIO(csv_content))
        job.row_count_raw = len(df_raw)
        db.commit()

        # Step A: Data Cleaning
        df_clean = clean_dataframe(df_raw)
        job.row_count_clean = len(df_clean)

        # Step B: Anomaly Detection
        df_analysed = detect_anomalies(df_clean)

        # Prepare records as dictionary list for database and LLM interaction
        records = df_analysed.to_dict(orient="records")

        # Step C: Batch LLM Classification for missing categories
        uncategorised_txns = [r for r in records if r.get('category') == 'Uncategorised']

        if uncategorised_txns:
            classified_txns = classify_transactions(uncategorised_txns)
            # Merge results back into the main records track
            classified_map = {t['txn_id']: t for t in classified_txns}
            for r in records:
                if r['txn_id'] in classified_map:
                    r.update(classified_map[r['txn_id']])

        # Persist transactions to database
        for r in records:
            txn = Transaction(
                job_id=job_id,
                txn_id=str(r.get('txn_id')) if pd.notna(r.get('txn_id')) else None,
                date=r.get('date'),
                merchant=r.get('merchant'),
                amount=r.get('amount'),
                currency=r.get('currency'),
                status=r.get('status'),
                category=r.get('category'),
                account_id=str(r.get('account_id')) if pd.notna(r.get('account_id')) else None,
                notes=r.get('notes') if pd.notna(r.get('notes')) else None,
                is_anomaly=r.get('is_anomaly', False),
                anomaly_reason=r.get('anomaly_reason'),
                llm_category=r.get('llm_category'),
                llm_raw_response=r.get('llm_raw_response'),
                llm_failed=r.get('llm_failed', False)
            )
            db.add(txn)

        # Step D: LLM Narrative Summary
        # Compute baseline aggregates to provide to the analyst LLM
        total_inr = sum((r.get('amount') or 0.0) for r in records if r.get('currency') == 'INR')
        total_usd = sum((r.get('amount') or 0.0) for r in records if r.get('currency') == 'USD')
        anomaly_count = sum(1 for r in records if r.get('is_anomaly'))

        merchant_counts = {}
        for r in records:
            merchant = r.get('merchant')
            if merchant:
                merchant_counts[merchant] = merchant_counts.get(merchant, 0) + 1
        top_merchants = [
            merchant for merchant, _ in sorted(
                merchant_counts.items(),
                key=lambda item: (-item[1], item[0])
            )[:3]
        ]

        # Combine default or AI categories to establish a true category breakdown
        category_breakdown = {}
        for r in records:
            category = r.get('category')
            if category == 'Uncategorised' and r.get('llm_category'):
                category = r.get('llm_category')
            category = category or 'Other'
            category_breakdown[category] = category_breakdown.get(category, 0.0) + (r.get('amount') or 0.0)

        stats = {
            "total_inr": float(total_inr),
            "total_usd": float(total_usd),
            "anomaly_count": anomaly_count,
            "top_merchants": top_merchants,
            "category_breakdown": category_breakdown
        }

        summary_data = generate_narrative_summary(stats)

        # Build JobSummary payload (use calculated stats as fallbacks if LLM fails)
        summary_record = JobSummary(
            job_id=job_id,
            total_spend_inr=summary_data.get("total_spend_inr", float(total_inr)) if summary_data else float(total_inr),
            total_spend_usd=summary_data.get("total_spend_usd", float(total_usd)) if summary_data else float(total_usd),
            top_merchants=summary_data.get("top_merchants", top_merchants) if summary_data else top_merchants,
            anomaly_count=summary_data.get("anomaly_count", anomaly_count) if summary_data else anomaly_count,
            narrative=summary_data.get("narrative",
                                       "Summary narrative unavailable.") if summary_data else "Failed to generate narrative summary.",
            risk_level=summary_data.get("risk_level", "medium") if summary_data else "high"
        )
        db.add(summary_record)

        # Finalize job tracking metadata
        job.status = "completed"
        job.completed_at = datetime.utcnow()

    except Exception as e:
        db.rollback()
        job.status = "failed"
        job.error_message = str(e)
        print(f"Pipeline execution failure on job {job_id}: {e}")
    finally:
        db.commit()
        db.close()
