# app/main.py

from fastapi import FastAPI, APIRouter

# --- NOVAS IMPORTAÇÕES DA API V2 ---
from app.api.v2 import transcriptions as v2_transcriptions
from app.api.v2 import narrations as v2_narrations
from app.api.v2 import auth as v2_auth
from app.api.v2 import settings as v2_settings
# --- FIM DAS NOVAS IMPORTAÇÕES ---

# Criação da Instância Principal da Aplicação
app = FastAPI(
    title="PySub_Dub - API de Transcrição e Narração",
    description="""
API completa para transcrição, narração e dublagem de mídias.

**API V2:**

* `/api/v2/auth`: Autenticação e gerenciamento de chaves de API.
* `/api/v2/transcriptions`: Gerenciamento de tarefas de transcrição.
* `/api/v2/narrations`: Gerenciamento de narrações, TTS e merge de vídeos.
* `/api/v2/settings`: Configurações da aplicação.
    """,
    version="2.0.0",
    contact={
        "name": "Daniel Santos",
        "url": "https://dsantosinfo.com.br",
    },
)

# --- ROTEADOR PRINCIPAL DA V2 ---
api_v2_router = APIRouter(prefix="/api/v2")

api_v2_router.include_router(v2_auth.router)
api_v2_router.include_router(v2_settings.router)
api_v2_router.include_router(v2_transcriptions.router)
api_v2_router.include_router(v2_narrations.router)

# Endpoint para criar narração a partir de uma transcrição.
# Ele pertence logicamente a /transcriptions/{id}/narrate
api_v2_router.include_router(v2_narrations.transcriptions_router)

app.include_router(api_v2_router)
# --- FIM DA CONFIGURAÇÃO DA V2 ---


# --- Endpoint Raiz para Health Check ---
@app.get("/", tags=["Root"], summary="Verifica a saúde da API")
async def read_root():
    """
    Endpoint básico que pode ser usado para verificar se a API
    está online e respondendo a requisições.
    """
    return {"status": "ok", "message": "Bem-vindo à API PySub_Dub v2!"}