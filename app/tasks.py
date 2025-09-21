# app/tasks.py

import logging
import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime

from app.core.celery_app import celery_app
from app.services.transcription_service import TranscriptionService
from app.database import AsyncSessionLocal
from app.schemas.job import JobStatus
from app import crud

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_db_session_context():
    """Cria e gere uma sessão de banco de dados assíncrona."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def _transcribe_chunk_async(service: TranscriptionService, chunk_path: Path) -> tuple[str, float, str]:
    """Função auxiliar assíncrona para transcrever um único pedaço de áudio."""
    srt_content = await service.transcribe_chunk(chunk_path)
    duration = await service.get_audio_duration(chunk_path)
    # Retornamos também o caminho do chunk para garantir a ordenação correta
    return srt_content, duration, str(chunk_path)


async def _notify_webhook_async(job):
    """Função auxiliar assíncrona para enviar notificação de webhook."""
    if not job.callback_url:
        return
    logger.info(f"Webhook para o Job ID {job.id} notificado (simulado) para {job.callback_url}")


@celery_app.task(bind=True, name="tasks:process_video_pipeline", max_retries=3, default_retry_delay=120)
def process_video_pipeline(self, job_id: str):
    """
    Tarefa Celery síncrona que orquestra todo o pipeline de transcrição de forma assíncrona.
    """
    
    async def _run_full_pipeline_async():
        """O fluxo de trabalho completo executado dentro de um único event loop e uma única sessão de DB."""
        job_uuid = uuid.UUID(job_id)
        service = TranscriptionService()
        audio_file_path = None
        audio_chunk_paths = []
        
        async with get_db_session_context() as db:
            try:
                # 1. SETUP INICIAL E ATUALIZAÇÃO DE STATUS
                job = await crud.get_job(db, job_id=job_uuid)
                if not job:
                    logger.error(f"Job não encontrado com ID: {job_id}")
                    return

                await crud.update_job(db, job=job, update_data={
                    "status": JobStatus.PREPARING,
                    "processing_started_at": datetime.utcnow(),
                    "retry_count": self.request.retries
                })
                
                groq_api_key = await crud.get_decrypted_groq_api_key(db)
                if not groq_api_key:
                    raise RuntimeError("API Key da Groq não configurada.")
                
                service = TranscriptionService(groq_api_key=groq_api_key)
                video_path = Path(job.storage_path)

                # 2. EXTRAÇÃO E DIVISÃO DO ÁUDIO
                audio_file_path = await service.extract_and_optimize_audio(video_path)
                audio_chunk_paths = await service.split_audio(audio_file_path)
                
                duration = await service.get_audio_duration(audio_file_path)
                await crud.update_job(db, job=job, update_data={"audio_duration_seconds": duration})

                # 3. TRANSCRIÇÃO EM PARALELO
                transcription_tasks = [_transcribe_chunk_async(service, chunk) for chunk in audio_chunk_paths]
                results = await asyncio.gather(*transcription_tasks, return_exceptions=True)

                # 4. PROCESSAMENTO DOS RESULTADOS
                await crud.update_job(db, job=job, update_data={"status": JobStatus.PROCESSING})

                successful_results = [res for res in results if not isinstance(res, Exception)]
                failed_results = [res for res in results if isinstance(res, Exception)]

                if failed_results:
                    logger.warning(f"Job {job_id}: {len(failed_results)} fragmento(s) falharam.")

                if not successful_results:
                    raise RuntimeError(f"Todos os fragmentos falharam. Último erro: {results[-1]}")

                # 5. COMBINAÇÃO E FINALIZAÇÃO
                successful_results.sort(key=lambda r: r[2]) 
                srt_data = [(res[0], res[1]) for res in successful_results]
                final_srt_content = service.combine_and_offset_srts(srt_data)
                srt_path = await service.save_srt_file(final_srt_content, job_id)

                # 6. ATUALIZAÇÃO FINAL DO BANCO E NOTIFICAÇÃO
                update_data = {"status": JobStatus.COMPLETED, "result_srt_path": str(srt_path), "processing_ended_at": datetime.utcnow()}
                if failed_results:
                    update_data["error_details"] = f"Transcrição concluída com {len(failed_results)} falha(s)."
                
                await crud.update_job(db, job=job, update_data=update_data)
                await _notify_webhook_async(job)

            except Exception as e:
                # 7. TRATAMENTO DE ERRO GLOBAL
                error_message = f"Falha no pipeline do Job ID {job_id}: {str(e)}"
                logger.error(error_message, exc_info=True)
                job_to_fail = await crud.get_job(db, job_id=job_uuid)
                if job_to_fail:
                    await crud.update_job(db, job=job_to_fail, update_data={"status": JobStatus.FAILED, "error_details": error_message, "processing_ended_at": datetime.utcnow()})
                raise RuntimeError(error_message)

            finally:
                # 8. LIMPEZA DOS ARQUIVOS TEMPORÁRIOS
                files_to_clean = []
                if audio_file_path: files_to_clean.append(audio_file_path)
                if audio_chunk_paths: files_to_clean.extend(audio_chunk_paths)
                if files_to_clean:
                    service.cleanup_files(*files_to_clean)

    # Ponto de entrada síncrono da tarefa Celery
    try:
        asyncio.run(_run_full_pipeline_async())
    except Exception as exc:
        self.retry(exc=exc)
