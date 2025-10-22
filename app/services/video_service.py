# app/services/video_service.py

import logging
import uuid
from pathlib import Path

import ffmpeg

from app.core.config import settings

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class VideoService:
    """
    Serviço para encapsular operações de processamento de vídeo usando ffmpeg.
    """
    def __init__(self):
        self.shared_dir = Path(settings.SHARED_FILES_DIR)
        self.shared_dir.mkdir(exist_ok=True, parents=True)

    def merge_video_with_audio(self, video_path: Path, audio_path: Path) -> Path:
        """
        Une um arquivo de vídeo com uma nova faixa de áudio.

        O stream de vídeo é copiado diretamente (sem re-codificação) para máxima
        velocidade e para preservar a qualidade original. A faixa de áudio original
        do vídeo é descartada e substituída pela nova.

        Args:
            video_path: Caminho para o arquivo de vídeo original (.mp4, etc.).
            audio_path: Caminho para o arquivo de áudio da narração (.mp3).

        Returns:
            O caminho para o novo arquivo de vídeo gerado.
        
        Raises:
            RuntimeError: Se o processo do ffmpeg falhar.
        """
        output_filename = f"merged_{uuid.uuid4()}.mp4"
        output_path = self.shared_dir / output_filename
        
        logger.info(f"Iniciando merge. Vídeo: '{video_path}', Áudio: '{audio_path}'")
        logger.info(f"Arquivo de saída será: '{output_path}'")

        try:
            input_video = ffmpeg.input(str(video_path))
            input_audio = ffmpeg.input(str(audio_path))

            # Mapeia o stream de vídeo do primeiro input e o stream de áudio do segundo
            (
                ffmpeg.output(
                    input_video.video,    # Usa o vídeo do primeiro arquivo
                    input_audio.audio,    # Usa o áudio do segundo arquivo
                    str(output_path),
                    vcodec='copy',        # Copia o vídeo sem re-codificar (rápido)
                    acodec='aac',         # Re-codifica o áudio para AAC (padrão para MP4)
                    shortest=None,        # Usa a flag '-shortest' para finalizar quando o stream mais curto acabar
                )
                .overwrite_output()
                .run(cmd="ffmpeg", capture_stdout=True, capture_stderr=True)
            )

        except ffmpeg.Error as e:
            error_message = f"Falha no ffmpeg ao unir os arquivos: {e.stderr.decode()}"
            logger.error(error_message, exc_info=True)
            raise RuntimeError(error_message)

        logger.info(f"Merge concluído com sucesso. Vídeo final salvo em: {output_path}")
        return output_path