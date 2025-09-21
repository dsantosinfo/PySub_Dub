# app/crud.py

import uuid
from datetime import datetime
from typing import List, Tuple, Optional

# Adicionado 'delete' para a nova função
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

# Models, Schemas, and Utils
from app.models.job import Job
from app.models.user import User, ApiKey
from app.models.settings import Settings
from app.schemas.job import JobCreate, JobStatus
from app.schemas.user import UserCreate
from app.core.encryption import encryptor
from app.security import (
    get_password_hash,
    generate_api_key,
    get_api_key_hash
)

# --- Settings CRUD ---

async def get_setting(db: AsyncSession, key: str) -> Optional[Settings]:
    """Busca uma configuração pelo sua chave."""
    result = await db.execute(select(Settings).where(Settings.key == key))
    return result.scalars().first()

async def create_or_update_setting(db: AsyncSession, key: str, value: str) -> Settings:
    """Cria ou atualiza uma configuração. Criptografa o valor se for a GROQ_API_KEY."""
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
    """Busca e descriptografa a chave da API da Groq."""
    setting = await get_setting(db, "GROQ_API_KEY")
    if setting and setting.value:
        return encryptor.decrypt(setting.value)
    return None

# --- User and ApiKey CRUD ---

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Busca um usuário pelo email."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalars().first()

async def create_user(db: AsyncSession, user_in: UserCreate) -> User:
    """Cria um novo usuário."""
    hashed_password = get_password_hash(user_in.password)
    db_user = User(email=user_in.email, hashed_password=hashed_password)
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

async def create_api_key_for_user(db: AsyncSession, user: User) -> Tuple[str, ApiKey]:
    """Gera e armazena uma nova chave de API para um usuário."""
    plaintext_key, prefix = generate_api_key()
    hashed_key = get_api_key_hash(plaintext_key)
    
    db_api_key = ApiKey(
        user_id=user.id,
        hashed_key=hashed_key,
        prefix=prefix
    )
    db.add(db_api_key)
    await db.commit()
    await db.refresh(db_api_key)
    # Retorna a chave em texto plano APENAS NESTE MOMENTO.
    return plaintext_key, db_api_key

# --- NOVA FUNÇÃO PARA O LOGIN ---
async def reset_and_create_api_key_for_user(db: AsyncSession, user: User) -> Tuple[str, ApiKey]:
    """
    Apaga todas as chaves de API existentes de um usuário e cria uma nova.
    Garante que apenas uma chave válida exista após o login (rotação de chave).
    """
    # Etapa 1: Apagar todas as chaves de API antigas do usuário em uma única operação.
    delete_stmt = delete(ApiKey).where(ApiKey.user_id == user.id)
    await db.execute(delete_stmt)
    
    # Etapa 2: Chamar a função existente para criar uma nova chave.
    # A função create_api_key_for_user já faz o commit da nova chave.
    plaintext_key, new_api_key_obj = await create_api_key_for_user(db, user=user)
    
    return plaintext_key, new_api_key_obj


async def get_user_by_api_key(db: AsyncSession, key: str) -> Optional[User]:
    """Busca um usuário associado a uma chave de API."""
    # O prefixo agora é 'sk_' conforme definido em security.py
    # Adicionamos uma verificação simples para evitar buscas desnecessárias.
    if "_" not in key:
        return None
        
    hashed_key = get_api_key_hash(key)
    result = await db.execute(
        select(User)
        .join(ApiKey)
        .where(ApiKey.hashed_key == hashed_key, User.is_active == True) # Adicionado is_active
    )
    user = result.scalars().first()
    
    if user:
        # Atualiza o 'last_used_at' da chave (melhor se feito em background)
        prefix = key.split("_")[1][:8]
        key_result = await db.execute(select(ApiKey).where(ApiKey.prefix == prefix))
        api_key_obj = key_result.scalars().first()
        if api_key_obj:
            api_key_obj.last_used_at = datetime.utcnow()
            await db.commit()
            
    return user

# --- Job CRUD ---
# (O restante do arquivo permanece o mesmo)

async def create_job(
    db: AsyncSession, *, user: User, file: UploadFile, job_in: JobCreate, storage_path: str
) -> Job:
    """Cria um novo registro de job no banco de dados."""
    db_job = Job(
        user_id=user.id,
        original_video_filename=file.filename,
        storage_path=storage_path,
        status=JobStatus.PENDING,
        priority=job_in.priority,
        callback_url=str(job_in.callback_url) if job_in.callback_url else None
    )
    db.add(db_job)
    await db.commit()
    await db.refresh(db_job)
    return db_job

async def get_job(db: AsyncSession, job_id: uuid.UUID, user: Optional[User] = None) -> Optional[Job]:
    """Busca um job pelo seu ID, opcionalmente filtrando por usuário."""
    query = select(Job).where(Job.id == job_id)
    if user:
        query = query.where(Job.user_id == user.id)
    
    result = await db.execute(query)
    return result.scalars().first()

async def get_jobs_by_user(
    db: AsyncSession, user: User, skip: int = 0, limit: int = 100
) -> Tuple[List[Job], int]:
    """Busca uma lista paginada de jobs para um usuário específico."""
    count_query = select(func.count()).select_from(Job).where(Job.user_id == user.id)
    total = (await db.execute(count_query)).scalar_one()

    query = (
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    jobs = result.scalars().all()
    return list(jobs), total

async def update_job(db: AsyncSession, job: Job, update_data: dict) -> Job:
    """Atualiza um registro de job com novos dados."""
    for key, value in update_data.items():
        setattr(job, key, value)
    await db.commit()
    await db.refresh(job)
    return job