# app/services/transcription_service_sync.py

import logging
import re
import uuid
from pathlib import Path
from datetime import timedelta
from typing import Optional, List

import ffmpeg
import librosa
import numpy as np
import soundfile as sf
from groq import Groq

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SRT_BLOCK_PATTERN = re.compile(
    r'(\d+)\n'
    r'(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n'
    r'([\s\S]*?)(?=\n\n|\Z)',
    re.MULTILINE
)
SRT_TIME_PATTERN = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})')
CHUNK_MAX_DURATION_S = 120
SILENCE_TOP_DB = 40
MAX_FILE_SIZE_MB = 25


class TranscriptionServiceSync:
    """
    Versão síncrona do serviço de transcrição, projetada para ser executada
    em um worker Celery com pool gevent.
    """

    def __init__(self, groq_api_key: Optional[str] = None):
        if groq_api_key:
            # Usa o cliente síncrono da Groq
            self.groq_client = Groq(api_key=groq_api_key)
        self.shared_dir = Path(settings.SHARED_FILES_DIR)
        self.shared_dir.mkdir(exist_ok=True, parents=True)

    def cleanup_files(self, *files: Path):
        """Remove de forma segura uma lista de arquivos temporários."""
        logger.info(f"Iniciando limpeza de {len(files)} arquivos.")
        for file_path in files:
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                    logger.info(f"Arquivo temporário removido: {file_path}")
                except OSError as e:
                    logger.error(f"Erro ao remover o arquivo {file_path}: {e}")

    def extract_and_optimize_audio(self, video_path: Path) -> Path:
        """Extrai o áudio de forma síncrona e bloqueante."""
        audio_output_path = self.shared_dir / f"audio_{uuid.uuid4()}.mp3"
        logger.info(f"Iniciando extração de áudio de {video_path} para {audio_output_path}")
        try:
            ffmpeg.input(str(video_path)).output(
                str(audio_output_path),
                acodec='libmp3lame', ar='16000', ac=1, q='2', vn=None, y=None
            ).run(cmd="ffmpeg", capture_stdout=True, capture_stderr=True)
        except ffmpeg.Error as e:
            raise RuntimeError(f"Falha ao extrair áudio: {e.stderr.decode()}")
        logger.info("Extração de áudio concluída.")
        return audio_output_path

    def split_audio(self, audio_path: Path) -> List[Path]:
        """Divide um arquivo de áudio de forma síncrona e bloqueante."""
        logger.info(f"Verificando a necessidade de divisão para o áudio: {audio_path}")
        max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        if audio_path.stat().st_size <= max_size_bytes:
            logger.info("Arquivo de áudio dentro do limite. Não é necessário dividir.")
            return [audio_path]

        logger.info("Arquivo de áudio excede o limite. Iniciando divisão.")
        y, sr = librosa.load(audio_path, sr=16000, mono=True)
        intervals = librosa.effects.split(y, top_db=SILENCE_TOP_DB)
        if not intervals.size:
            return [audio_path]

        chunk_paths, current_chunk = [], np.array([])
        max_samples, audio_base = int(CHUNK_MAX_DURATION_S * sr), audio_path.stem
        for i, (start, end) in enumerate(intervals):
            segment = y[start:end]
            if len(current_chunk) + len(segment) > max_samples and len(current_chunk) > 0:
                chunk_path = self.shared_dir / f"{audio_base}_chunk_{i:04d}.flac"
                sf.write(str(chunk_path), current_chunk, sr)
                chunk_paths.append(chunk_path)
                current_chunk = segment
            else:
                current_chunk = np.concatenate([current_chunk, segment])

        if len(current_chunk) > 0:
            chunk_path = self.shared_dir / f"{audio_base}_chunk_{len(intervals):04d}.flac"
            sf.write(str(chunk_path), current_chunk, sr)
            chunk_paths.append(chunk_path)

        logger.info(f"Áudio dividido em {len(chunk_paths)} fragmentos.")
        return chunk_paths

    def get_audio_duration(self, audio_path: Path) -> float:
        """Obtém a duração do áudio de forma síncrona."""
        try:
            return librosa.get_duration(path=audio_path)
        except Exception:
            return 0.0

    def transcribe_chunk(self, audio_chunk_path: Path) -> str:
        """Envia um fragmento de áudio para a API da Groq de forma síncrona."""
        logger.info(f"Enviando fragmento para transcrição: {audio_chunk_path}")
        try:
            with open(audio_chunk_path, "rb") as file:
                transcription = self.groq_client.audio.transcriptions.create(
                    file=(audio_chunk_path.name, file.read()),
                    model="whisper-large-v3",
                    response_format="verbose_json",
                    language="pt",
                    timestamp_granularities=["segment"]
                )
            return self._convert_segments_to_srt(transcription.to_dict())
        except Exception as e:
            logger.error(f"Erro ao transcrever o fragmento {audio_chunk_path}: {e}", exc_info=True)
            raise RuntimeError(f"Falha na comunicação com a API da Groq: {e}")

    def save_srt_file(self, content: str, job_id: str) -> Path:
        """Salva o conteúdo SRT final em um arquivo de forma síncrona."""
        srt_path = self.shared_dir / f"result_{job_id}.srt"
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Arquivo SRT final salvo em: {srt_path}")
        return srt_path

    def _convert_segments_to_srt(self, transcription_result: dict) -> str:
        """Converte a resposta de segmentos da API da Groq para o formato SRT."""
        if not transcription_result or 'segments' not in transcription_result:
            return ""
        srt_blocks = []
        for segment in transcription_result['segments']:
            index = segment['id'] + 1
            start_time = self._format_srt_time(timedelta(seconds=segment['start']))
            end_time = self._format_srt_time(timedelta(seconds=segment['end']))
            text = segment['text'].strip()
            if text:
                srt_blocks.append(f"{index}\n{start_time} --> {end_time}\n{text}")
        return "\n\n".join(srt_blocks) + "\n\n" if srt_blocks else ""

    def combine_and_offset_srts(self, srt_data: list[tuple[str, float]]) -> str:
        """Combina múltiplos SRTs com offset de tempo."""
        final_blocks, cumulative_duration, index = [], timedelta(), 1
        for srt_content, duration in srt_data:
            if not srt_content or not srt_content.strip():
                cumulative_duration += timedelta(seconds=duration)
                continue
            for block in SRT_BLOCK_PATTERN.finditer(srt_content):
                final_blocks.append(self._offset_srt_block(block, cumulative_duration, index))
                index += 1
            cumulative_duration += timedelta(seconds=duration)
        return "\n\n".join(final_blocks) + "\n\n"

    def _parse_srt_time(self, time_str: str) -> timedelta:
        match = SRT_TIME_PATTERN.match(time_str)
        if not match: return timedelta(0)
        h, m, s, ms = map(int, match.groups())
        return timedelta(hours=h, minutes=m, seconds=s, milliseconds=ms)

    def _format_srt_time(self, td: timedelta) -> str:
        total_seconds = int(td.total_seconds())
        ms = td.microseconds // 1000
        h, m, s = total_seconds // 3600, (total_seconds % 3600) // 60, total_seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def _offset_srt_block(self, block: re.Match, offset_td: timedelta, new_index: int) -> str:
        start_ts = self._parse_srt_time(block.group(2)) + offset_td
        end_ts = self._parse_srt_time(block.group(3)) + offset_td
        text = block.group(4)
        return f"{new_index}\n{self._format_srt_time(start_ts)} --> {self._format_srt_time(end_ts)}\n{text}"