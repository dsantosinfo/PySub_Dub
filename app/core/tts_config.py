# app/core/tts_config.py

from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
MODELS_BASE_PATH = PROJECT_ROOT / "tts_models"

# --- Motor Local: Piper TTS ---
PIPER_TTS_VOICES = {
    "cadu": str(MODELS_BASE_PATH / "pt_BR-cadu-synthesis-medium" / "model.onnx"),
    "edresson": str(MODELS_BASE_PATH / "pt_BR-edresson-low" / "model.onnx"),
    "faber": str(MODELS_BASE_PATH / "pt_BR-faber-medium" / "model.onnx"),
    "jeff": str(MODELS_BASE_PATH / "pt_BR-jeff-medium" / "model.onnx"),
}

# --- Motor em Nuvem: Microsoft Edge TTS ---
# Lista expandida com todas as vozes neurais padrão para pt-BR
EDGE_TTS_VOICES = {
    "br-antonio": "pt-BR-AntonioNeural",
    "br-brenda": "pt-BR-BrendaNeural",
    "br-donato": "pt-BR-DonatoNeural",
    "br-elza": "pt-BR-ElzaNeural",
    "br-fabio": "pt-BR-FabioNeural",
    "br-francisca": "pt-BR-FranciscaNeural",
    "br-giovanna": "pt-BR-GiovannaNeural",
    "br-humberto": "pt-BR-HumbertoNeural",
    "br-julio": "pt-BR-JulioNeural",
    "br-leila": "pt-BR-LeilaNeural",
    "br-leticia": "pt-BR-LeticiaNeural",
    "br-manuela": "pt-BR-ManuelaNeural",
    "br-nicolau": "pt-BR-NicolauNeural",
    "br-thalita": "pt-BR-ThalitaNeural",
    "br-valerio": "pt-BR-ValerioNeural",
    "br-yara": "pt-BR-YaraNeural",
}

# --- Dicionário unificado de vozes disponíveis ---
AVAILABLE_TTS_VOICES = {**PIPER_TTS_VOICES, **EDGE_TTS_VOICES}

# Lista de nomes de vozes para validação na API
VOICE_NAMES = list(AVAILABLE_TTS_VOICES.keys())