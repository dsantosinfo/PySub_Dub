# app/models/narration.py

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional # <<< Verifique esta importação
from sqlalchemy import (
    String, Integer, Text, DateTime, func, ForeignKey, Enum as SQLAlchemyEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseUUID
from app.schemas.narration import NarrationStatus, MergeStatus

if TYPE_CHECKING:
    from .job import Job

class Narration(BaseUUID):
    __tablename__ = "narrations"

    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True, unique=False)
    
    # --- A LINHA CORRIGIDA ---
    job: Mapped[Optional["Job"]] = relationship("Job", back_populates="narration")
    # -------------------------

    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[NarrationStatus] = mapped_column(
        SQLAlchemyEnum(NarrationStatus, name="narration_status_enum", create_type=True),
        default=NarrationStatus.PENDING, nullable=False, index=True
    )
    voice: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # ... (o resto do arquivo como na mensagem anterior)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    processing_ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_audio_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    
    merge_status: Mapped[Optional[MergeStatus]] = mapped_column(
        SQLAlchemyEnum(MergeStatus, name="merge_status_enum", create_type=True),
        nullable=True, index=True
    )
    result_video_path: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    merge_error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Narration(id={self.id}, status='{self.status.value}', merge_status='{self.merge_status}')>"