# app/api/v2/narrations.py

import uuid
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db_session
from app.security import get_current_user
from app.models.user import User
from app.schemas.job import JobStatus
from app.schemas.narration import (
    Narration,
    NarrationCreate,
    NarrationStatus,
    TextToSpeechRequest,
    MergeStatus,
    MergeStatusResponse, # <-- Importa o novo schema
)
from app.core.celery_app import celery_app
from app.tasks import (
    process_narration_pipeline,
    process_tts_pipeline,
    process_merge_pipeline,
)
from app.core.tts_config import VOICE_NAMES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/narrations", tags=["V2 - Narrations"])


# Helper para determinar a task correta baseada no estado da narração
def _get_task_by_narration_state(narration: crud.Narration):
    if narration.merge_status in [MergeStatus.MERGE_FAILED, MergeStatus.MERGE_PENDING]:
        return process_merge_pipeline
    if narration.job_id:  # Narração a partir de um job
        return process_narration_pipeline
    if narration.text_content:  # Narração a partir de texto (TTS)
        return process_tts_pipeline
    return None


@router.get("/voices", response_model=List[str], summary="Lista as vozes de narração disponíveis")
async def list_available_voices():
    """Retorna uma lista com os nomes das vozes disponíveis para TTS."""
    return VOICE_NAMES


@router.post(
    "/text-to-speech",
    response_model=Narration,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cria uma tarefa de narração a partir de um texto (TTS)",
)
async def direct_text_to_speech(
    payload: TextToSpeechRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Recebe um texto e uma voz, cria uma tarefa de narração e a enfileira para processamento.
    O resultado é um arquivo de áudio MP3.
    """
    narration = await crud.create_narration_from_text(
        db=db, text=payload.text, voice=payload.voice
    )
    process_tts_pipeline.apply_async(args=[str(narration.id)])
    return narration


@router.get(
    "/{narration_id}", response_model=Narration, summary="Consulta uma tarefa de narração"
)
async def get_narration_details(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Obtém o status detalhado de uma tarefa de narração específica."""
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tarefa de narração não encontrada."
        )
    return narration


@router.get(
    "/{narration_id}/audio",
    response_class=FileResponse,
    summary="Baixa o arquivo de áudio da narração (MP3)",
)
async def download_narration_file(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fornece o download do arquivo MP3 resultante de uma tarefa de narração concluída.
    """
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarefa de narração não encontrada.")
    if narration.status != NarrationStatus.COMPLETED or not narration.result_audio_path:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A narração não está pronta ou falhou. Status: {narration.status.value}",
        )
    result_path = Path(narration.result_audio_path)
    if not result_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de áudio não encontrado no servidor.",
        )
    return FileResponse(
        path=result_path,
        media_type="audio/mpeg",
        filename=f"narration_{narration.id}.mp3",
    )


# --- NOVO ENDPOINT ADICIONADO ---
@router.get(
    "/{narration_id}/merge",
    response_model=MergeStatusResponse,
    summary="Consulta o status do processo de merge"
)
async def get_merge_status(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Consulta o status específico da tarefa de merge de vídeo para uma narração.
    Retorna um objeto leve contendo apenas o ID e o status atual do merge.
    """
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tarefa de narração não encontrada."
        )
    return narration


@router.post(
    "/{narration_id}/merge",
    response_model=Narration,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inicia a junção da narração com o vídeo original",
)
async def merge_narration_with_video(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Para narrações geradas a partir de uma transcrição, esta rota inicia a tarefa
    de unir o áudio narrado com o vídeo original, criando um vídeo dublado.
    """
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Narração não encontrada.")
    if not narration.job:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O merge só é aplicável a narrações geradas a partir de um vídeo.",
        )
    if narration.status != NarrationStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A narração de áudio precisa estar 'COMPLETED' para iniciar o merge.",
        )
    if narration.merge_status not in [None, MergeStatus.MERGE_FAILED]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Um processo de merge já foi iniciado ou concluído. Status: {narration.merge_status}",
        )
    updated_narration = await crud.update_narration(
        db, narration, {"merge_status": MergeStatus.MERGE_PENDING}
    )
    process_merge_pipeline.apply_async(args=[str(narration.id)])
    return updated_narration


@router.get(
    "/{narration_id}/video",
    response_class=FileResponse,
    summary="Baixa o vídeo final com o áudio narrado (dublado)",
)
async def download_merged_video(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Fornece o download do vídeo MP4 final após um processo de merge bem-sucedido.
    """
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Narração não encontrada.")
    if (
        narration.merge_status != MergeStatus.MERGE_COMPLETED
        or not narration.result_video_path
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O vídeo final não está pronto ou o merge falhou. Status: {narration.merge_status}",
        )
    result_path = Path(narration.result_video_path)
    if not result_path.is_file():
        logger.error(f"Arquivo de vídeo final não encontrado no caminho: {result_path}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Arquivo de vídeo final não encontrado no servidor.",
        )
    return FileResponse(
        path=result_path,
        media_type="video/mp4",
        filename=f"dubbed_video_{narration.id}.mp4",
    )


@router.post(
    "/{narration_id}/cancel",
    response_model=Narration,
    summary="Cancela uma tarefa de narração em andamento",
)
async def cancel_narration(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Cancela uma tarefa de narração ou merge que ainda está na fila ou em processamento."""
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Narração não encontrada.")

    update_data = {}
    if narration.merge_status in [MergeStatus.MERGE_PENDING, MergeStatus.MERGE_PROCESSING]:
        update_data["merge_status"] = MergeStatus.MERGE_CANCELED
    elif narration.status in [NarrationStatus.PENDING, NarrationStatus.PROCESSING]:
        update_data["status"] = NarrationStatus.CANCELED
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tarefa não pode ser cancelada no estado atual (Status: {narration.status.value}, Merge: {narration.merge_status}).",
        )

    celery_app.control.revoke(str(narration.id), terminate=True, signal="SIGKILL")
    updated_narration = await crud.update_narration(db, narration=narration, update_data=update_data)
    return updated_narration


@router.post(
    "/{narration_id}/retry",
    response_model=Narration,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Tenta novamente uma tarefa de narração que falhou",
)
async def retry_narration(
    narration_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """Reprocessa uma tarefa de narração ou merge que resultou em falha."""
    narration = await crud.get_narration(db, narration_id=narration_id, user=current_user)
    if not narration:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Narração não encontrada.")

    task_to_run = _get_task_by_narration_state(narration)
    update_data = {}

    if narration.merge_status == MergeStatus.MERGE_FAILED:
        update_data = {"merge_status": MergeStatus.MERGE_PENDING, "merge_error_details": None}
    elif narration.status == NarrationStatus.FAILED:
        update_data = {"status": NarrationStatus.PENDING, "error_details": None}
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A tarefa só pode ser reprocessada se estiver no estado 'FAILED' ou 'MERGE_FAILED'.",
        )

    if not task_to_run:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Não foi possível determinar a tarefa correta para o reprocessamento.",
        )

    updated_narration = await crud.update_narration(db, narration=narration, update_data=update_data)
    task_to_run.apply_async(args=[str(updated_narration.id)])
    return updated_narration


# --- Roteador separado para o endpoint aninhado ---
transcriptions_router = APIRouter()

@transcriptions_router.post(
    "/{transcription_id}/narrate",
    response_model=Narration,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Cria uma tarefa de narração para uma transcrição concluída",
    tags=["V2 - Transcriptions"]
)
async def create_narration_for_transcription(
    transcription_id: uuid.UUID,
    payload: NarrationCreate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    job = await crud.get_job(db, job_id=transcription_id, user=current_user)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transcrição não encontrada.")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A transcrição precisa estar 'COMPLETED' para gerar uma narração.",
        )
    if not job.result_srt_path or not Path(job.result_srt_path).is_file():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Arquivo SRT de resultado não encontrado."
        )
    if await crud.get_narration_by_job_id(db, job_id=job.id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uma narração para esta transcrição já existe.",
        )
    narration = await crud.create_narration(db, job=job, voice=payload.voice)
    process_narration_pipeline.apply_async(args=[str(narration.id)])
    return narration