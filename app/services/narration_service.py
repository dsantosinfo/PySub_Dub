# app/services/narration_service.py

import logging
import re
import uuid
import wave
import asyncio  # Importação necessária para edge-tts
from pathlib import Path
from datetime import timedelta
from typing import List, Dict, Any

from pydub import AudioSegment
from piper.voice import PiperVoice
import edge_tts  # Importação da nova biblioteca

from app.core.config import settings
from app.core.tts_config import PIPER_TTS_VOICES, EDGE_TTS_VOICES

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SRT_BLOCK_PATTERN = re.compile(r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n|\Z)', re.MULTILINE)
SRT_TIME_PATTERN = re.compile(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})')
MIN_SILENCE_MS = 150

class NarrationService:
    def __init__(self):
        self.shared_dir = Path(settings.SHARED_FILES_DIR)
        self.temp_dir = self.shared_dir / "temp"
        self.shared_dir.mkdir(exist_ok=True, parents=True)
        self.temp_dir.mkdir(exist_ok=True, parents=True)
        if not hasattr(NarrationService, '_voice_cache'):
            NarrationService._voice_cache: Dict[str, PiperVoice] = {}

    # --- NOVO MÉTODO PRIVADO PARA EDGE TTS (ASSÍNCRONO) ---
    async def _synthesize_edge_async(self, text: str, voice_name: str) -> AudioSegment:
        """Lida com a síntese de fala usando a biblioteca assíncrona edge-tts."""
        tmp_mp3_path = self.temp_dir / f"{uuid.uuid4()}.mp3"
        try:
            communicate = edge_tts.Communicate(text, voice_name)
            await communicate.save(str(tmp_mp3_path))
            return AudioSegment.from_mp3(tmp_mp3_path)
        finally:
            if tmp_mp3_path.exists():
                tmp_mp3_path.unlink()

    # --- NOVO MÉTODO PRIVADO PARA PIPER TTS (SÍNCRONO) ---
    def _synthesize_piper(self, text: str, voice_name: str) -> AudioSegment:
        """Lida com a síntese de fala usando a biblioteca local piper-tts."""
        tmp_wav_path = self.temp_dir / f"{uuid.uuid4()}.wav"
        try:
            voice_model = self._get_voice(voice_name)
            with wave.open(str(tmp_wav_path), "wb") as wav_file:
                voice_model.synthesize_wav(text, wav_file)
            return AudioSegment.from_wav(tmp_wav_path)
        finally:
            if tmp_wav_path.exists():
                tmp_wav_path.unlink()

    # --- MÉTODO 'synthesize' ATUALIZADO PARA AGIR COMO UM ROTEADOR ---
    def synthesize(self, text: str, voice: str) -> AudioSegment:
        """
        Verifica a voz solicitada e chama o motor de TTS apropriado.
        """
        if voice in EDGE_TTS_VOICES:
            logger.info(f"Roteando para o motor Edge TTS com a voz: {voice}")
            full_voice_name = EDGE_TTS_VOICES[voice]
            # Como nosso worker gevent é síncrono, usamos asyncio.run() para
            # executar a função assíncrona do edge-tts.
            return asyncio.run(self._synthesize_edge_async(text, full_voice_name))

        elif voice in PIPER_TTS_VOICES:
            logger.info(f"Roteando para o motor Piper TTS com a voz: {voice}")
            return self._synthesize_piper(text, voice)
        else:
            raise ValueError(f"Voz desconhecida ou motor não suportado: '{voice}'.")

    def _get_voice(self, voice_name: str) -> PiperVoice:
        if voice_name in NarrationService._voice_cache:
            return NarrationService._voice_cache[voice_name]
        model_path = PIPER_TTS_VOICES.get(voice_name)
        if not model_path:
            raise ValueError(f"Voz Piper desconhecida: '{voice_name}'.")
        logger.info(f"Carregando modelo Piper TTS: {model_path}")
        voice = PiperVoice.load(model_path)
        NarrationService._voice_cache[voice_name] = voice
        return voice

    # O restante do arquivo (funções de SRT, create_narration_adaptive, etc.) permanece inalterado.
    def _parse_srt_time(self, time_str: str) -> timedelta:
        match = SRT_TIME_PATTERN.match(time_str)
        if not match: return timedelta()
        h, m, s, ms = map(int, match.groups())
        return timedelta(hours=h, minutes=m, seconds=s, milliseconds=ms)

    def _parse_srt_file(self, srt_path: Path) -> List[Dict[str, Any]]:
        content = srt_path.read_text(encoding='utf-8')
        blocks = []
        for match in SRT_BLOCK_PATTERN.finditer(content):
            start_time = self._parse_srt_time(match.group(2))
            end_time = self._parse_srt_time(match.group(3))
            text = re.sub(r'<[^>]+>', '', match.group(4)).strip()
            if text:
                blocks.append({'start': start_time, 'end': end_time, 'text': text})
        return blocks

    def create_narration_adaptive(self, srt_path: Path, voice: str) -> Path:
        final_audio_path = self.shared_dir / f"narration_{uuid.uuid4()}.mp3"
        logger.info("Iniciando geração de narração com linha do tempo ADAPTATIVA...")

        srt_blocks = self._parse_srt_file(srt_path)
        if not srt_blocks:
            raise ValueError("Arquivo SRT vazio.")

        video_duration_ms = srt_blocks[-1]['end'].total_seconds() * 1000
        logger.info("Fase 1: Gerando todos os clipes de áudio para análise...")
        audio_clips = [self.synthesize(block['text'], voice) for block in srt_blocks]
        
        total_speech_duration_ms = sum(len(clip) for clip in audio_clips)
        logger.info("Fase 2: Calculando estratégia de compressão de tempo...")
        total_silence_duration_ms = 0
        last_end = timedelta(0)
        for block in srt_blocks:
            silence = block['start'] - last_end
            total_silence_duration_ms += silence.total_seconds() * 1000
            last_end = block['end']

        total_content_duration_ms = total_speech_duration_ms + total_silence_duration_ms
        overflow_ms = total_content_duration_ms - video_duration_ms
        
        speedup_factor = 1.0
        silence_shrink_factor = 1.0

        if overflow_ms > 0:
            logger.warning(f"Déficit de tempo detectado: {overflow_ms:.0f}ms a mais.")
            available_silence_to_shrink = total_silence_duration_ms - (len(srt_blocks) * MIN_SILENCE_MS)
            if available_silence_to_shrink > 0:
                if overflow_ms <= available_silence_to_shrink:
                    silence_shrink_factor = (available_silence_to_shrink - overflow_ms) / available_silence_to_shrink
                    logger.info(f"Resolvendo com compressão de silêncio. Fator: {silence_shrink_factor:.2f}")
                    overflow_ms = 0
                else:
                    overflow_ms -= available_silence_to_shrink
                    silence_shrink_factor = 0
                    logger.warning("Compressão de silêncio não foi suficiente.")

            if overflow_ms > 0:
                speedup_factor = (total_speech_duration_ms) / (total_speech_duration_ms - overflow_ms)
                logger.info(f"Resolvendo com aceleração de áudio. Fator: {speedup_factor:.2f}")

        logger.info("Fase 3: Montando a linha do tempo final...")
        timeline = AudioSegment.silent(duration=0)
        last_original_end = timedelta(0)

        for i, block in enumerate(srt_blocks):
            original_silence_duration = (block['start'] - last_original_end).total_seconds() * 1000
            new_silence_duration = max(MIN_SILENCE_MS, original_silence_duration * silence_shrink_factor)
            timeline += AudioSegment.silent(duration=new_silence_duration)

            clip = audio_clips[i]
            if speedup_factor > 1.0:
                clip = clip.speedup(playback_speed=speedup_factor)
            
            timeline += clip
            last_original_end = block['end']

        if len(timeline) > video_duration_ms:
            timeline = timeline[:video_duration_ms]
        else:
            timeline += AudioSegment.silent(duration=(video_duration_ms - len(timeline)))
            
        logger.info(f"Exportando áudio final para: {final_audio_path}")
        timeline.export(final_audio_path, format="mp3", bitrate="128k")
        return final_audio_path