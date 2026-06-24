from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime

try:
    from pydantic import ConfigDict
except ImportError:
    ConfigDict = None


class ORMBaseModel(BaseModel):
    if ConfigDict:
        model_config = ConfigDict(from_attributes=True)
    else:
        class Config:
            orm_mode = True


class JobResponse(ORMBaseModel):
    job_id: str
    status: str
    message: str

class JobStatusResponse(ORMBaseModel):
    job_id: str
    status: str
    filename: Optional[str]
    row_count_raw: Optional[int]
    row_count_clean: Optional[int]
    created_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    summary: Optional[dict] = None

class TransactionOut(ORMBaseModel):
    id: str
    txn_id: Optional[str]
    date: Optional[str]
    merchant: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    status: Optional[str]
    category: Optional[str]
    account_id: Optional[str]
    notes: Optional[str]
    is_anomaly: bool
    anomaly_reason: Optional[str]
    llm_category: Optional[str]

class JobResultsResponse(ORMBaseModel):
    job_id: str
    transactions: List[TransactionOut]
    anomalies: List[TransactionOut]
    category_breakdown: dict
    summary: Optional[dict]

class JobListItem(ORMBaseModel):
    job_id: str
    status: str
    filename: Optional[str]
    row_count_raw: Optional[int]
    created_at: Optional[datetime]
