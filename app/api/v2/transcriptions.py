# app/api/v2/transcriptions.py

import uuid
import logging
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db_session
from app.security import get_current_user
from app.models.user import User
from app.schemas.job import Job, JobCreate, JobList, JobStatus
from app.core.celery_app import celery_app
from app.tasks import process_video_pipeline, process_audio_pipeline
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transcriptions",
    tags=["V2 - Transcriptions"]
)

# HELPER FUNCTION
def _get_task_by_media_type(media_type: str):
    if media_type == 'video':
        return process_video_pipeline
    elif media_type == 'audio':
        return process_audio_pipeline
    return None

@router.post(
    "/",
    response_model=Job,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cria uma nova tarefa de transcrição"
)
async def create_transcription(
    job_in: JobCreate = Depends(),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user)
):
    media_type = None
    task_to_run = None

    if file.content_type and file.content_type.startswith("video/"):
        media_type = 'video'
        task_to_run = process_video_pipeline
    elif file.content_type and file.content_type in ["audio/mpeg", "audio/mp3"]:
        media_type = 'audio'
        task_to_run = process_audio_pipeline
    else:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=f"Tipo de arquivo '{file.content_type}' não suportado.")

# Cria o objeto de caminho (Path object)
    file_path_obj = Path(settings.SHARED_FILES_DIR) / f"upload_{uuid.uuid4()}{Path(file.filename or '').suffix}"
    
    try:
        # Usa o objeto de caminho para salvar o arquivo no sistema operacional local (Windows)
        with open(file_path_obj, "wb") as buffer:
            buffer.write(await file.read())
    except Exception:
        logger.error(f"Falha ao salvar o arquivo para o usuário {current_user.email}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Falha ao salvar o arquivo.")

    # Converte o caminho para o formato POSIX (com '/') ANTES de salvar no banco
    db_storage_path = file_path_obj.as_posix()

    job = await crud.create_job(db=db, user=current_user, file=file, job_in=job_in, storage_path=db_storage_path, media_type=media_type)
    task_to_run.apply_async(args=[str(job.id)], priority=job.priority)
    return job

@router.get("/", response_model=JobList, summary="Lista as tarefas de transcrição")
async def list_transcriptions(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    jobs, total = await crud.get_jobs_by_user(db, user=current_user, skip=skip, limit=limit)
    return {"jobs": jobs, "total": total}

@router.get("/{transcription_id}", response_model=Job, summary="Consulta uma tarefa de transcrição")
async def get_transcription(transcription_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    job = await crud.get_job(db, job_id=transcription_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcrição não encontrada.")
    return job

@router.get("/{transcription_id}/srt", response_class=FileResponse, summary="Baixa o arquivo SRT resultante")
async def download_transcription_srt(transcription_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    job = await crud.get_job(db, job_id=transcription_id, user=current_user)
    if not job or job.status != JobStatus.COMPLETED or not job.result_srt_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resultado da transcrição não encontrado ou não concluído.")
    
    result_path = Path(job.result_srt_path)
    if not result_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo de resultado não encontrado no servidor.")
    
    return FileResponse(path=result_path, media_type="application/x-subrip", filename=f"transcription_{job.id}.srt")

@router.delete("/{transcription_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deleta uma tarefa de transcrição")
async def delete_transcription(transcription_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    job = await crud.get_job(db, job_id=transcription_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcrição não encontrada.")
    
    if job.status in [JobStatus.PROCESSING, JobStatus.PREPARING]:
        celery_app.control.revoke(str(job.id), terminate=True, signal='SIGKILL')

    await crud.delete_job(db, job_to_delete=job)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.post("/{transcription_id}/cancel", response_model=Job, summary="Cancela uma tarefa de transcrição")
async def cancel_transcription(transcription_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    job = await crud.get_job(db, job_id=transcription_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcrição não encontrada.")
    
    if job.status not in [JobStatus.PENDING, JobStatus.PREPARING, JobStatus.PROCESSING]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A tarefa não pode ser cancelada pois já está no estado '{job.status.value}'.")

    celery_app.control.revoke(str(job.id), terminate=True, signal='SIGKILL')
    updated_job = await crud.update_job(db, job=job, update_data={"status": JobStatus.CANCELED})
    return updated_job

@router.post("/{transcription_id}/retry", response_model=Job, summary="Tenta novamente uma tarefa de transcrição que falhou")
async def retry_transcription(transcription_id: uuid.UUID, db: AsyncSession = Depends(get_db_session), current_user: User = Depends(get_current_user)):
    job = await crud.get_job(db, job_id=transcription_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcrição não encontrada.")

    if job.status != JobStatus.FAILED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"A tarefa só pode ser reprocessada se estiver no estado 'FAILED'. Estado atual: '{job.status.value}'.")
    
    task_to_run = _get_task_by_media_type(job.media_type)
    if not task_to_run:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Tipo de mídia desconhecido ('{job.media_type}') para reprocessamento.")

    updated_job = await crud.update_job(db, job=job, update_data={"status": JobStatus.PENDING, "error_details": None})
    task_to_run.apply_async(args=[str(updated_job.id)], priority=updated_job.priority)
    return updated_job