# app/main.py

from fastapi import FastAPI
from app.api import endpoints

# --- Criação da Instância Principal da Aplicação ---
app = FastAPI(
    title="PySub_Dub - API de Transcrição de Vídeo",
    description="""
    Uma API assíncrona para transcrever e dublar arquivos de vídeo longos.

    **Fluxo de Trabalho:**
    1. Crie um usuário inicial via CLI (`docker-compose exec api python run.py create-user ...`).
    2. Use o endpoint `POST /auth/login` com seu e-mail e senha para obter uma chave de API.
    3. Na documentação, clique no botão "Authorize" e cole sua nova chave (`sk_...`) para autenticar as requisições.
    4. Use o endpoint `PUT /settings/groq-api-key` para configurar a chave da API da Groq.
    5. Envie vídeos para transcrição através do endpoint `POST /jobs`.
    6. Monitore o status do job com o endpoint `GET /jobs/{job_id}`.
    7. Baixe o resultado (`.srt`) quando o job estiver concluído.
    """,
    version="1.2.0", # Versão incrementada para refletir a nova funcionalidade
    contact={
        "name": "Daniel Santos",
        "url": "https://dsantosinfo.com.br",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# --- Inclusão dos Roteadores ---

# Adiciona as rotas relacionadas à autenticação (login)
app.include_router(
    endpoints.auth_router, 
    prefix="/api/v1/auth", 
    tags=["Authentication"]
)

# Adiciona as rotas relacionadas aos jobs de transcrição
app.include_router(endpoints.router, prefix="/api/v1/jobs", tags=["Jobs"])

# Adiciona as rotas relacionadas às configurações do sistema
app.include_router(
    endpoints.settings_router, 
    prefix="/api/v1/settings", 
    tags=["Settings"]
)


# --- Endpoint Raiz para Health Check ---
@app.get("/", tags=["Root"], summary="Verifica a saúde da API")
async def read_root():
    """
    Endpoint básico que pode ser usado para verificar se a API
    está online e respondendo a requisições.
    """
    return {"status": "ok", "message": "Bem-vindo à API PySub_Dub!"}