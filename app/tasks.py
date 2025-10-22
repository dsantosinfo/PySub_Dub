# app/tasks.py

import logging
import uuid
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime
from typing import Callable, Dict

from app.core.celery_app import celery_app
from app.schemas.job import JobStatus
from app.schemas.narration import NarrationStatus, MergeStatus

from app.database_sync import SessionLocalSync
from app import crud_sync
from app.services.narration_service import NarrationService
from app.services.transcription_service_sync import TranscriptionServiceSync
from app.services.video_service import VideoService


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@contextmanager
def get_db_sync_session_context():
    db = SessionLocalSync()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def _execute_transcription_pipeline_sync(job_id: str, retry_count: int, is_video: bool):
    job_uuid = uuid.UUID(job_id)
    service: TranscriptionServiceSync = None
    audio_file_path, audio_chunk_paths = None, []
    with get_db_sync_session_context() as db:
        try:
            job = crud_sync.get_job_sync(db, job_id=job_uuid)
            if not job: return
            crud_sync.update_job_sync(db, job=job, update_data={"status": JobStatus.PREPARING, "processing_started_at": datetime.utcnow(), "retry_count": retry_count})
            groq_api_key = crud_sync.get_decrypted_groq_api_key_sync(db)
            if not groq_api_key: raise RuntimeError("API Key da Groq não configurada.")
            service = TranscriptionServiceSync(groq_api_key=groq_api_key)
            media_path = Path(job.storage_path)
            if is_video: audio_file_path = service.extract_and_optimize_audio(media_path)
            else: audio_file_path = media_path
            audio_chunk_paths = service.split_audio(audio_file_path)
            duration = service.get_audio_duration(audio_file_path)
            crud_sync.update_job_sync(db, job=job, update_data={"audio_duration_seconds": duration, "status": JobStatus.PROCESSING})
            results = []
            for chunk_path in audio_chunk_paths:
                try:
                    srt_content = service.transcribe_chunk(chunk_path)
                    chunk_duration = service.get_audio_duration(chunk_path)
                    results.append((srt_content, chunk_duration, str(chunk_path)))
                except Exception as chunk_exc:
                    logger.warning(f"Falha ao transcrever o fragmento {chunk_path}: {chunk_exc}")
            if not results: raise RuntimeError("Todos os fragmentos falharam.")
            results.sort(key=lambda r: r[2])
            srt_data = [(res[0], res[1]) for res in results]
            final_srt = service.combine_and_offset_srts(srt_data)
            srt_path = service.save_srt_file(final_srt, job_id)
            update_data = {"status": JobStatus.COMPLETED, "result_srt_path": str(srt_path), "processing_ended_at": datetime.utcnow()}
            if len(results) != len(audio_chunk_paths):
                update_data["error_details"] = f"Concluído com {len(audio_chunk_paths) - len(results)} falhas."
            crud_sync.update_job_sync(db, job=job, update_data=update_data)
        except Exception:
            raise
        finally:
            if service:
                chunks_to_clean = [p for p in audio_chunk_paths if p != audio_file_path]
                if chunks_to_clean: service.cleanup_files(*chunks_to_clean)
                if is_video and audio_file_path: service.cleanup_files(audio_file_path)

def _handle_task_failure(task_name: str, obj_id: uuid.UUID, exception: Exception):
    error_message = f"Falha na task '{task_name}' para o ID {obj_id}: {exception}"
    logger.error(error_message, exc_info=True)
    
    with get_db_sync_session_context() as db:
        update_logic: Dict[str, Callable] = {
            "narration": (crud_sync.get_narration_sync, crud_sync.update_narration_sync, {"status": NarrationStatus.FAILED, "error_details": error_message}),
            "tts": (crud_sync.get_narration_sync, crud_sync.update_narration_sync, {"status": NarrationStatus.FAILED, "error_details": error_message}),
            "merge": (crud_sync.get_narration_sync, crud_sync.update_narration_sync, {"merge_status": MergeStatus.MERGE_FAILED, "merge_error_details": error_message}),
            "video": (crud_sync.get_job_sync, crud_sync.update_job_sync, {"status": JobStatus.FAILED, "error_details": error_message}),
            "audio": (crud_sync.get_job_sync, crud_sync.update_job_sync, {"status": JobStatus.FAILED, "error_details": error_message}),
        }

        for key, (getter, updater, payload) in update_logic.items():
            if key in task_name:
                obj = getter(db, obj_id)
                if obj: updater(db, obj, payload)
                break

@celery_app.task(bind=True, name="tasks:process_video_pipeline", max_retries=3, default_retry_delay=120)
def process_video_pipeline(self, job_id: str):
    try:
        _execute_transcription_pipeline_sync(job_id=job_id, retry_count=self.request.retries, is_video=True)
    except Exception as exc:
        _handle_task_failure(self.name, uuid.UUID(job_id), exc)
        self.retry(exc=exc)

@celery_app.task(bind=True, name="tasks:process_audio_pipeline", max_retries=3, default_retry_delay=120)
def process_audio_pipeline(self, job_id: str):
    try:
        _execute_transcription_pipeline_sync(job_id=job_id, retry_count=self.request.retries, is_video=False)
    except Exception as exc:
        _handle_task_failure(self.name, uuid.UUID(job_id), exc)
        self.retry(exc=exc)

@celery_app.task(bind=True, name="tasks:process_narration_pipeline", max_retries=3, default_retry_delay=180)
def process_narration_pipeline(self, narration_id: str):
    try:
        with get_db_sync_session_context() as db:
            narration = crud_sync.get_narration_sync(db, narration_id=uuid.UUID(narration_id))
            if not (narration and narration.job and narration.job.result_srt_path):
                raise ValueError("Narração, job ou arquivo SRT associado não encontrado.")
            crud_sync.update_narration_sync(db, narration=narration, update_data={"status": NarrationStatus.PROCESSING, "processing_started_at": datetime.utcnow(), "retry_count": self.request.retries})
            service = NarrationService()
            final_audio_path = service.create_narration_adaptive(srt_path=Path(narration.job.result_srt_path), voice=narration.voice)
            crud_sync.update_narration_sync(db, narration=narration, update_data={"status": NarrationStatus.COMPLETED, "result_audio_path": str(final_audio_path), "processing_ended_at": datetime.utcnow()})
    except Exception as e:
        _handle_task_failure(self.name, uuid.UUID(narration_id), e)
        self.retry(exc=e)

@celery_app.task(bind=True, name="tasks:process_tts_pipeline", max_retries=3, default_retry_delay=180)
def process_tts_pipeline(self, narration_id: str):
    try:
        with get_db_sync_session_context() as db:
            narration = crud_sync.get_narration_sync(db, narration_id=uuid.UUID(narration_id))
            if not (narration and narration.text_content):
                raise ValueError("Narração ou conteúdo de texto não encontrado.")
            crud_sync.update_narration_sync(db, narration=narration, update_data={"status": NarrationStatus.PROCESSING, "processing_started_at": datetime.utcnow(), "retry_count": self.request.retries})
            service = NarrationService()
            audio_segment = service.synthesize(text=narration.text_content, voice=narration.voice)
            final_audio_path = service.shared_dir / f"narration_{narration.id}.mp3"
            audio_segment.export(final_audio_path, format="mp3", bitrate="128k")
            crud_sync.update_narration_sync(db, narration=narration, update_data={"status": NarrationStatus.COMPLETED, "result_audio_path": str(final_audio_path), "processing_ended_at": datetime.utcnow()})
    except Exception as e:
        _handle_task_failure(self.name, uuid.UUID(narration_id), e)
        self.retry(exc=e)

@celery_app.task(bind=True, name="tasks:process_merge_pipeline", max_retries=3, default_retry_delay=300)
def process_merge_pipeline(self, narration_id: str):
    narration_uuid = uuid.UUID(narration_id)
    try:
        with get_db_sync_session_context() as db:
            narration = crud_sync.get_narration_sync(db, narration_id=narration_uuid)
            if not (narration and narration.job and narration.job.storage_path and narration.result_audio_path):
                raise ValueError("Pré-condições para o merge não atendidas (job, vídeo ou áudio faltando).")

            crud_sync.update_narration_sync(db, narration, {"merge_status": MergeStatus.MERGE_PROCESSING})
            video_service = VideoService()
            final_video_path = video_service.merge_video_with_audio(video_path=Path(narration.job.storage_path), audio_path=Path(narration.result_audio_path))
            crud_sync.update_narration_sync(db, narration, {"merge_status": MergeStatus.MERGE_COMPLETED, "result_video_path": str(final_video_path)})
    except Exception as e:
        _handle_task_failure(self.name, narration_uuid, e)
        self.retry(exc=e)