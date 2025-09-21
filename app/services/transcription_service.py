# app/services/transcription_service.py
import logging
import re
import asyncio
from pathlib import Path
from datetime import timedelta
import uuid
from typing import Optional

import ffmpeg
from groq import Groq, AsyncGroq
import librosa
import soundfile as sf
import numpy as np

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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


class TranscriptionService:
    def __init__(self, groq_api_key: Optional[str] = None):
        if groq_api_key:
            self.groq_client = AsyncGroq(api_key=groq_api_key)
        self.shared_dir = Path(settings.SHARED_FILES_DIR)
        self.shared_dir.mkdir(exist_ok=True, parents=True)

    def cleanup_files(self, *files: Path):
        """Remove de forma segura uma lista de arquivos temporários."""
        logging.info(f"Iniciando limpeza de {len(files)} arquivos.")
        for file_path in files:
            if file_path and file_path.exists():
                try:
                    file_path.unlink()
                    logging.info(f"Arquivo temporário removido: {file_path}")
                except OSError as e:
                    logging.error(f"Erro ao remover o arquivo {file_path}: {e}")

    async def extract_and_optimize_audio(self, video_path: Path) -> Path:
        """Extrai o áudio do vídeo em um formato otimizado (MP3, 16kHz, mono)."""
        audio_output_path = self.shared_dir / f"audio_{uuid.uuid4()}.mp3"
        logging.info(f"Iniciando extração de áudio de {video_path} para {audio_output_path}")
        
        def _run_ffmpeg():
            try:
                ffmpeg.input(str(video_path)).output(
                    str(audio_output_path),
                    acodec='libmp3lame',
                    ar='16000',
                    ac=1,
                    q='2',
                    vn=None,
                    y=None
                ).run(cmd="ffmpeg", capture_stdout=True, capture_stderr=True)
            except ffmpeg.Error as e:
                raise RuntimeError(f"Falha ao extrair áudio: {e.stderr.decode()}")

        await asyncio.to_thread(_run_ffmpeg)
        logging.info("Extração de áudio concluída.")
        return audio_output_path

    async def split_audio(self, audio_path: Path) -> list[Path]:
        """
        Divide um arquivo de áudio em fragmentos menores se o tamanho do arquivo
        exceder o limite definido (ex: 25MB).
        """
        logging.info(f"Verificando a necessidade de divisão para o áudio: {audio_path}")
        
        max_size_bytes = MAX_FILE_SIZE_MB * 1024 * 1024
        file_size_bytes = audio_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        if file_size_bytes <= max_size_bytes:
            logging.info(f"Arquivo de áudio com {file_size_mb:.2f}MB. Não é necessário dividir.")
            return [audio_path]

        logging.info(f"Arquivo de áudio com {file_size_mb:.2f}MB excede o limite de {MAX_FILE_SIZE_MB}MB. Iniciando divisão por silêncio.")

        def _run_librosa_split():
            y, sr = librosa.load(audio_path, sr=16000, mono=True)
            intervals = librosa.effects.split(y, top_db=SILENCE_TOP_DB)
            if not intervals.size:
                logging.warning("Não foram detectados pontos de silêncio para a divisão. Usando o arquivo completo.")
                return [audio_path]
            
            chunk_paths = []
            current_chunk = np.array([])
            max_samples = int(CHUNK_MAX_DURATION_S * sr)
            audio_base = audio_path.stem
            
            for i, (start, end) in enumerate(intervals):
                segment = y[start:end]
                if len(current_chunk) + len(segment) > max_samples and len(current_chunk) > 0:
                    chunk_filename = f"{audio_base}_chunk_{i:04d}_{uuid.uuid4().hex[:8]}.flac"
                    chunk_path = self.shared_dir / chunk_filename
                    sf.write(str(chunk_path), current_chunk, sr)
                    chunk_paths.append(chunk_path)
                    current_chunk = segment
                else:
                    current_chunk = np.concatenate([current_chunk, segment])
            
            if len(current_chunk) > 0:
                chunk_filename = f"{audio_base}_chunk_{len(intervals):04d}_{uuid.uuid4().hex[:8]}.flac"
                chunk_path = self.shared_dir / chunk_filename
                sf.write(str(chunk_path), current_chunk, sr)
                chunk_paths.append(chunk_path)

            return chunk_paths

        chunk_paths = await asyncio.to_thread(_run_librosa_split)
        logging.info(f"Áudio dividido em {len(chunk_paths)} fragmentos.")
        return chunk_paths

    async def get_audio_duration(self, audio_path: Path) -> float:
        try:
            return await asyncio.to_thread(librosa.get_duration, path=audio_path)
        except Exception:
            return 0.0

    async def transcribe_chunk(self, audio_chunk_path: Path) -> str:
        """Envia um fragmento de áudio para a API da Groq e retorna a legenda em SRT."""
        logging.info(f"Enviando fragmento para transcrição: {audio_chunk_path}")
        try:
            with open(audio_chunk_path, "rb") as file:
                transcription = await self.groq_client.audio.transcriptions.create(
                    file=(audio_chunk_path.name, file.read()),
                    model="whisper-large-v3",
                    # --- ALTERADO: Agora pedimos 'segment' para corresponder ao seu exemplo ---
                    response_format="verbose_json",
                    language="pt",
                    timestamp_granularities=["segment"]
                )
            # --- ALTERADO: Chama a nova função de conversão baseada em segmentos ---
            return self._convert_segments_to_srt(transcription.to_dict())
        except Exception as e:
            logging.error(f"Erro ao transcrever o fragmento {audio_chunk_path}: {e}", exc_info=True)
            raise RuntimeError(f"Falha na comunicação com a API da Groq: {e}")

    async def save_srt_file(self, content: str, job_id: str) -> Path:
        """Salva o conteúdo SRT final em um arquivo."""
        srt_path = self.shared_dir / f"result_{job_id}.srt"
        def _write_file():
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(content)
        await asyncio.to_thread(_write_file)
        logging.info(f"Arquivo SRT final salvo em: {srt_path}")
        return srt_path
    
    # --- NOVA FUNÇÃO ---
    def _convert_segments_to_srt(self, transcription_result: dict) -> str:
        """Converte a resposta de segmentos da API da Groq para o formato SRT."""
        if not transcription_result or 'segments' not in transcription_result:
            return ""

        srt_blocks = []
        for segment in transcription_result['segments']:
            # O ID do segmento já é fornecido, mas vamos usar um contador para garantir a sequência.
            index = segment['id'] + 1
            start_time = self._format_srt_time(timedelta(seconds=segment['start']))
            end_time = self._format_srt_time(timedelta(seconds=segment['end']))
            text = segment['text'].strip()
            
            if text:
                srt_blocks.append(f"{index}\n{start_time} --> {end_time}\n{text}")
        
        return "\n\n".join(srt_blocks) + "\n\n" if srt_blocks else ""

    def combine_and_offset_srts(self, srt_data: list[tuple[str, float]]) -> str:
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