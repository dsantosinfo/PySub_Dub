# app/models/job.py

import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Text, DateTime, func, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseUUID
from app.schemas.job import JobStatus

if TYPE_CHECKING:
    from .user import User

class Job(BaseUUID):
    """
    Modelo para a tabela 'jobs'.
    """
    __tablename__ = "jobs"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    user: Mapped["User"] = relationship("User", back_populates="jobs") 

    original_video_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    
    status: Mapped[JobStatus] = mapped_column(
        # ALTERADO: create_type=True garante que o SQLAlchemy gerencie o tipo ENUM
        # no banco de dados. Isso é essencial para a geração automática de
        # migrações futuras com Alembic.
        Enum(JobStatus, name="job_status_enum", create_type=True),
        default=JobStatus.PENDING,
        nullable=False,
        index=True
    )
    
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    processing_ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    audio_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    priority: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    callback_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    
    result_srt_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    def __repr__(self) -> str:
        return f"<Job(id={self.id}, status='{self.status.value}', user_id={self.user_id})>"