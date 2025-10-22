# app/schemas/narration.py

import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Literal, Optional

from app.core.tts_config import VOICE_NAMES

# -----------------------------------------------------------------------------
# ENUMs
# -----------------------------------------------------------------------------

class NarrationStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class MergeStatus(str, Enum):
    """Define os possíveis status para o processo de junção do vídeo."""
    MERGE_PENDING = "MERGE_PENDING"
    MERGE_PROCESSING = "MERGE_PROCESSING"
    MERGE_COMPLETED = "MERGE_COMPLETED"
    MERGE_FAILED = "MERGE_FAILED"
    MERGE_CANCELED = "MERGE_CANCELED"

# -----------------------------------------------------------------------------
# Schemas de Entrada
# -----------------------------------------------------------------------------

class NarrationCreate(BaseModel):
    """Schema para criar uma narração a partir de um Job/SRT."""
    voice: Literal[*VOICE_NAMES] = Field(
        default="edresson",
        description="A voz a ser usada para a narração.",
        examples=VOICE_NAMES
    )

class TextToSpeechRequest(BaseModel):
    """Schema para a requisição de TTS direto."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=3000,
        description="O texto a ser convertido em áudio. Limite de 3000 caracteres."
    )
    voice: Literal[*VOICE_NAMES] = Field(
        default="edresson",
        description="A voz a ser usada para a síntese de fala."
    )

# -----------------------------------------------------------------------------
# Schemas de Saída
# -----------------------------------------------------------------------------

class Narration(BaseModel):
    """
    Schema completo para representar um job de narração na resposta da API.
    """
    id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    status: NarrationStatus
    voice: str
    
    text_content: Optional[str] = None
    
    result_audio_path: Optional[str] = None
    error_details: Optional[str] = None
    retry_count: int
    
    merge_status: Optional[MergeStatus] = Field(None, description="Status do processo de junção do áudio com o vídeo original.")
    result_video_path: Optional[str] = Field(None, description="Caminho para o arquivo de vídeo final com o áudio narrado.")
    merge_error_details: Optional[str] = Field(None, description="Detalhes do erro, caso o processo de merge falhe.")
    
    created_at: datetime
    updated_at: datetime
    processing_started_at: Optional[datetime] = None
    processing_ended_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# --- NOVO SCHEMA DE RESPOSTA ADICIONADO ---
class MergeStatusResponse(BaseModel):
    """Schema de resposta para o endpoint de consulta de status do merge."""
    id: uuid.UUID  # <-- CORRIGIDO para corresponder ao modelo do DB
    merge_status: Optional[MergeStatus]

    class Config:
        from_attributes = True