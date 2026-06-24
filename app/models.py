from sqlalchemy import Column, String, Float, Boolean, Integer, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
from app.database import Base

def gen_uuid():
    return str(uuid.uuid4())

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=gen_uuid)
    filename = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, failed
    row_count_raw = Column(Integer, default=0)
    row_count_clean = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    transactions = relationship("Transaction", back_populates="job")
    summary = relationship("JobSummary", back_populates="job", uselist=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("jobs.id"))
    txn_id = Column(String, nullable=True)
    date = Column(String, nullable=True)
    merchant = Column(String, nullable=True)
    amount = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    status = Column(String, nullable=True)
    category = Column(String, nullable=True)
    account_id = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    is_anomaly = Column(Boolean, default=False)
    anomaly_reason = Column(Text, nullable=True)
    llm_category = Column(String, nullable=True)
    llm_raw_response = Column(Text, nullable=True)
    llm_failed = Column(Boolean, default=False)

    job = relationship("Job", back_populates="transactions")


class JobSummary(Base):
    __tablename__ = "job_summaries"

    id = Column(String, primary_key=True, default=gen_uuid)
    job_id = Column(String, ForeignKey("jobs.id"))
    total_spend_inr = Column(Float, default=0.0)
    total_spend_usd = Column(Float, default=0.0)
    top_merchants = Column(JSON, nullable=True)
    anomaly_count = Column(Integer, default=0)
    narrative = Column(Text, nullable=True)
    risk_level = Column(String, nullable=True)

    job = relationship("Job", back_populates="summary")