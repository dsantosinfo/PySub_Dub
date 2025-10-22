# app/crud.py

import uuid
from datetime import datetime
from typing import List, Tuple, Optional

from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app.models.job import Job
from app.models.user import User, ApiKey
from app.models.settings import Settings
from app.models.narration import Narration
from app.schemas.job import JobCreate, JobStatus
from app.schemas.narration import NarrationStatus
from app.schemas.user import UserCreate
from app.core.encryption import encryptor
from app.security import (
    get_password_hash,
    generate_api_key,
    get_api_key_hash
)

# ... (Seções de Settings, User, ApiKey e Job CRUD permanecem inalteradas) ...
async def get_setting(db: AsyncSession, key: str) -> Optional[Settings]:
    result = await db.execute(select(Settings).where(Settings.key == key))
    return result.scalars().first()
async def create_or_update_setting(db: AsyncSession, key: str, value: str) -> Settings:
    is_secret = key == "GROQ_API_KEY"
    value_to_store = encryptor.encrypt(value) if is_secret else value
    setting = await get_setting(db, key)
    if setting:
        setting.value = value_to_store
    else:
        setting = Settings(key=key, value=value_to_store)
        db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting
async def get_decrypted_groq_api_key(db: AsyncSession) -> Optional[str]:
    setting = await get_setting(db, "GROQ_API_KEY")
    if setting and setting.value:
        return encryptor.decrypt(setting.value)
    return None
async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()
async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    hashed_password = get_password_hash(user_in.password)
    db_user = User(email=user_in.email, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user
async def create_api_key_for_user(db: AsyncSession, user: User) -> Tuple[str, ApiKey]:
    plaintext_key, prefix = generate_api_key()
    hashed_key = get_api_key_hash(plaintext_key)
    db_api_key = ApiKey(user_id=user.id, hashed_key=hashed_key, prefix=prefix)
    db.add(db_api_key)
    await db.commit()
    await db.refresh(db_api_key)
    return plaintext_key, db_api_key
async def reset_and_create_api_key_for_user(db: AsyncSession, user: User) -> Tuple[str, ApiKey]:
    await db.execute(delete(ApiKey).where(ApiKey.user_id == user.id))
    plaintext_key, new_api_key_obj = await create_api_key_for_user(db, user=user)
    return plaintext_key, new_api_key_obj
async def get_user_by_api_key(db: AsyncSession, key: str) -> Optional[User]:
    if "_" not in key: return None
    hashed_key = get_api_key_hash(key)
    result = await db.execute(select(User).join(ApiKey).where(ApiKey.hashed_key == hashed_key, User.is_active == True))
    user = result.scalars().first()
    if user:
        prefix = key.split("_")[1][:8]
        key_result = await db.execute(select(ApiKey).where(ApiKey.prefix == prefix))
        api_key_obj = key_result.scalars().first()
        if api_key_obj:
            api_key_obj.last_used_at = datetime.utcnow()
            await db.commit()
    return user
async def create_job(db: AsyncSession, *, user: User, file: UploadFile, job_in: JobCreate, storage_path: str, media_type: str) -> Job:
    db_job = Job(user_id=user.id, original_video_filename=file.filename, storage_path=storage_path, media_type=media_type, status=JobStatus.PENDING, priority=job_in.priority, callback_url=str(job_in.callback_url) if job_in.callback_url else None)
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    return db_job
async def get_job(db: AsyncSession, job_id: uuid.UUID, user: Optional[User] = None) -> Optional[Job]:
    query = select(Job).options(selectinload(Job.narration)).where(Job.id == job_id)
    if user:
        query = query.where(Job.user_id == user.id)
    result = await db.execute(query)
    return result.scalars().first()
async def get_jobs_by_user(db: AsyncSession, user: User, skip: int = 0, limit: int = 100) -> Tuple[List[Job], int]:
    count_query = select(func.count()).select_from(Job).where(Job.user_id == user.id)
    total = (await db.execute(count_query)).scalar_one()
    query = (select(Job).where(Job.user_id == user.id).order_by(Job.created_at.desc()).offset(skip).limit(limit))
    result = await db.execute(query)
    return list(result.scalars().all()), total
async def update_job(db: AsyncSession, job: Job, update_data: dict) -> Job:
    for key, value in update_data.items():
        setattr(job, key, value)
    await db.commit()
    await db.refresh(job)
    return job
async def delete_job(db: AsyncSession, *, job_to_delete: Job) -> None:
    await db.delete(job_to_delete)
    await db.commit()

# --- Narration CRUD ---
async def create_narration(db: AsyncSession, *, job: Job, voice: str) -> Narration:
    db_narration = Narration(job_id=job.id, voice=voice, status=NarrationStatus.PENDING)
    db.add(db_narration)
    await db.commit()
    await db.refresh(db_narration)
    return db_narration
async def get_narration(db: AsyncSession, narration_id: uuid.UUID, user: Optional[User] = None) -> Optional[Narration]:
    query = select(Narration).options(selectinload(Narration.job)).where(Narration.id == narration_id)
    if user:
        # Garante que o usuário só possa acessar narrações de seus próprios jobs
        query = query.join(Job).where(Job.user_id == user.id)
    result = await db.execute(query)
    return result.scalars().first()
async def get_narration_by_job_id(db: AsyncSession, job_id: uuid.UUID) -> Optional[Narration]:
    result = await db.execute(select(Narration).where(Narration.job_id == job_id))
    return result.scalars().first()
async def update_narration(db: AsyncSession, narration: Narration, update_data: dict) -> Narration:
    for key, value in update_data.items():
        setattr(narration, key, value)
    await db.commit()
    await db.refresh(narration)
    return narration
async def create_narration_from_text(db: AsyncSession, *, text: str, voice: str) -> Narration:
    db_narration = Narration(text_content=text, voice=voice, status=NarrationStatus.PENDING, job_id=None)
    db.add(db_narration)
    await db.commit()
    await db.refresh(db_narration)
    return db_narration

# --- NOVA FUNÇÃO DE DELEÇÃO ---
async def delete_narration(db: AsyncSession, *, narration_to_delete: Narration) -> None:
    """Deleta um registro de narração."""
    await db.delete(narration_to_delete)
    await db.commit()