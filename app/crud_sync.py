# app/crud_sync.py

import uuid
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session, selectinload

from app.core.encryption import encryptor
from app.models.job import Job
from app.models.narration import Narration
from app.models.settings import Settings
# --- INÍCIO DA CORREÇÃO ---
# Importamos o modelo 'User' para que o SQLAlchemy possa resolver
# o relacionamento definido no modelo 'Job'.
from app.models.user import User
# --- FIM DA CORREÇÃO ---


# --- Settings CRUD (Síncrono) ---

def get_setting_sync(db: Session, key: str) -> Optional[Settings]:
    """
    Busca uma configuração pela sua chave de forma síncrona.
    Essencial para a task de transcrição obter a chave da API da Groq.
    """
    return db.query(Settings).filter(Settings.key == key).first()


def get_decrypted_groq_api_key_sync(db: Session) -> Optional[str]:
    """Busca e descriptografa a chave da API da Groq de forma síncrona."""
    setting = get_setting_sync(db, "GROQ_API_KEY")
    if setting and setting.value:
        return encryptor.decrypt(setting.value)
    return None


# --- Job CRUD (Síncrono) ---

def get_job_sync(db: Session, job_id: uuid.UUID) -> Optional[Job]:
    """
    Busca um job pelo seu ID de forma síncrona.
    Usado no início de todas as tasks para obter o objeto do job.
    """
    # Esta consulta agora funcionará, pois o SQLAlchemy conhece o modelo 'User'.
    return (
        db.query(Job)
        .options(selectinload(Job.narration))
        .filter(Job.id == job_id)
        .first()
    )


def update_job_sync(db: Session, job: Job, update_data: Dict[str, Any]) -> Job:
    """
    Atualiza um registro de job com novos dados de forma síncrona.
    O commit é tratado pelo context manager da task.
    """
    for key, value in update_data.items():
        setattr(job, key, value)
    db.add(job)
    db.flush()
    db.refresh(job)
    return job


# --- Narration CRUD (Síncrono) ---
# (O restante do arquivo permanece inalterado)

def get_narration_sync(db: Session, narration_id: uuid.UUID) -> Optional[Narration]:
    """
    Busca uma narração pelo seu ID de forma síncrona.
    """
    return (
        db.query(Narration)
        .options(selectinload(Narration.job))
        .filter(Narration.id == narration_id)
        .first()
    )


def update_narration_sync(db: Session, narration: Narration, update_data: Dict[str, Any]) -> Narration:
    """
    Atualiza um registro de narração com novos dados de forma síncrona.
    O commit é tratado pelo context manager da task.
    """
    for key, value in update_data.items():
        setattr(narration, key, value)
    db.add(narration)
    db.flush()
    db.refresh(narration)
    return narration