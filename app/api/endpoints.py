# app/api/endpoints.py

import uuid
import logging
from pathlib import Path

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    status,
    Depends,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db_session
from app.security import get_current_user, verify_password
from app.models.user import User
from app.schemas.job import Job, JobCreate, JobList, JobStatus
from app.schemas.settings import GroqApiKeyUpdate 
from app.schemas.user import UserLogin, ApiKeyResponse
# --- ALTERAÇÃO NA IMPORTAÇÃO DA TAREFA ---
from app.tasks import process_video_pipeline
from app.core.config import settings

# Garante que o diretório de uploads exista
Path(settings.SHARED_FILES_DIR).mkdir(exist_ok=True, parents=True)

logger = logging.getLogger(__name__)

# --- Roteadores da Aplicação ---
router = APIRouter()
settings_router = APIRouter()
auth_router = APIRouter()


# ===============================================================
# ENDPOINT DE AUTENTICAÇÃO
# ===============================================================

@auth_router.post(
    "/login",
    response_model=ApiKeyResponse,
    summary="Autentica o usuário e retorna uma nova chave de API",
    description="""
    Forneça seu e-mail e senha para fazer login. 
    Se as credenciais forem válidas, todas as suas chaves de API antigas serão invalidadas
    e uma **nova chave de API** será retornada para uso em requisições subsequentes.
    """
)
async def login_for_api_key(
    payload: UserLogin,
    db: AsyncSession = Depends(get_db_session)
):
    user = await crud.get_user_by_email(db, email=payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    new_api_key, _ = await crud.reset_and_create_api_key_for_user(db, user=user)
    return ApiKeyResponse(api_key=new_api_key)


# ===============================================================
# ENDPOINTS DE JOBS
# ===============================================================

@router.post(
    "/",
    response_model=Job,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Envia um vídeo para transcrição",
)
async def create_transcription_job(
    job_in: JobCreate = Depends(),
    file: UploadFile = File(..., description="Arquivo de vídeo a ser transcrito."),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    if not file.content_type or not file.content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo de arquivo não suportado. Envie um vídeo."
        )
    
    groq_key = await crud.get_decrypted_groq_api_key(db)
    if not groq_key:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail="A chave da API da Groq não foi configurada. Por favor, configure-a via endpoint PUT /api/v1/settings/groq-api-key antes de criar um job."
        )

    file_suffix = Path(file.filename).suffix.lower() if file.filename else '.tmp'
    storage_path = Path(settings.SHARED_FILES_DIR) / f"upload_{uuid.uuid4()}{file_suffix}"
    
    try:
        with open(storage_path, "wb") as buffer:
            buffer.write(await file.read())
        logger.info(f"Arquivo salvo em: {storage_path} para o usuário {current_user.email}")
    except Exception as e:
        logger.error(f"Falha ao salvar o arquivo: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Falha ao salvar o arquivo."
        )

    job = await crud.create_job(
        db=db, user=current_user, file=file, job_in=job_in, storage_path=str(storage_path)
    )

    # --- ALTERAÇÃO NA CHAMADA DA TAREFA ---
    # Agora chama a nova tarefa orquestradora
    process_video_pipeline.apply_async(
        args=[str(job.id)], 
        priority=job.priority
    )
    
    return job

# (O restante do arquivo permanece exatamente o mesmo)
@router.get("/", response_model=JobList, summary="Lista os jobs do usuário")
async def list_jobs(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    jobs, total = await crud.get_jobs_by_user(db, user=current_user, skip=skip, limit=limit)
    return {"jobs": jobs, "total": total}

@router.get("/{job_id}", response_model=Job, summary="Obtém o status detalhado de um job")
async def get_job_details(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    job = await crud.get_job(db, job_id=job_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    return job

@router.get(
    "/{job_id}/download", 
    response_class=FileResponse, 
    summary="Baixa o arquivo de legenda (SRT)"
)
async def download_result_file(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    job = await crud.get_job(db, job_id=job_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado")
    
    if job.status != JobStatus.COMPLETED or not job.result_srt_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O resultado não está pronto ou o job falhou. Status atual: {job.status.value}"
        )

    result_path = Path(job.result_srt_path)
    if not result_path.is_file():
        logger.error(f"Arquivo SRT não encontrado no caminho esperado: {result_path} para o Job ID: {job_id}")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de resultado não encontrado no servidor.")

    filename = f"transcription_{job.id}.srt"
    return FileResponse(
        path=result_path,
        media_type="application/x-subrip",
        filename=filename
    )

# ===============================================================
# ENDPOINTS DE CONFIGURAções (SETTINGS)
# ===============================================================

@settings_router.put(
    "/groq-api-key",
    status_code=status.HTTP_200_OK,
    summary="Define ou atualiza a chave da API da Groq",
    response_model=dict
)
async def update_groq_api_key(
    payload: GroqApiKeyUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    await crud.create_or_update_setting(
        db, key="GROQ_API_KEY", value=payload.api_key
    )
    
    return {"message": "Chave da API da Groq foi salva e criptografada com sucesso."}