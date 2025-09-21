# app/schemas/job.py
from pydantic import BaseModel, Field, HttpUrl
from enum import Enum
import uuid
from typing import List # 'Optional' não é mais necessário aqui
from datetime import datetime

class JobStatus(str, Enum):
    PENDING = "PENDING"
    PREPARING = "PREPARING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class JobCreate(BaseModel):
    priority: int | None = Field( # Corrigido
        default=5,
        description="Prioridade do job (1=alta, 5=normal, 10=baixa)."
    )
    callback_url: HttpUrl | None = Field( # Corrigido
        default=None,
        description="URL para notificação via webhook ao concluir o job.",
        examples=["https://example.com/webhook/job-done"]
    )

class Job(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    status: JobStatus
    original_video_filename: str
    
    priority: int
    callback_url: HttpUrl | None = None # Corrigido
    
    error_details: str | None = None # Corrigido
    retry_count: int
    
    audio_duration_seconds: float | None = None # Corrigido
    
    result_srt_path: str | None = None # Corrigido

    created_at: datetime
    updated_at: datetime
    processing_started_at: datetime | None = None # Corrigido
    processing_ended_at: datetime | None = None # Corrigido
    
    class Config:
        from_attributes = True

class JobList(BaseModel):
    jobs: List[Job]
    total: int

class JobCreateResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus = JobStatus.PENDING
    message: str = "Job recebido e enfileirado para preparação."