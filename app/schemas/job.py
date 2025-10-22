# app/schemas/job.py

from pydantic import BaseModel, Field, HttpUrl
from enum import Enum
import uuid
from typing import List
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class JobCreate(BaseModel):
    priority: int | None = Field(default=5)
    callback_url: HttpUrl | None = Field(default=None)

class Job(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: JobStatus
    original_video_filename: str
    
    # --- NOVO CAMPO ADICIONADO ---
    media_type: str = Field(description="Tipo da mídia original ('video' ou 'audio').")
    
    priority: int
    callback_url: HttpUrl | None = None
    error_details: str | None = None
    retry_count: int
    audio_duration_seconds: float | None = None
    result_srt_path: str | None = None
    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None = None
    processing_ended_at: datetime | None = None
    
    class Config:
        from_attributes = True

class JobList(BaseModel):
    jobs: List[Job]
    total: int

class JobCreateResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus = JobStatus.PENDING
    message: str = "Job recebido e enfileirado para preparação."