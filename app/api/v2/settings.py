# app/api/v2/settings.py

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db_session
from app.security import get_current_user
from app.models.user import User
from app.schemas.settings import GroqApiKeyUpdate

router = APIRouter(prefix="/settings", tags=["V2 - Settings"])


@router.put(
    "/groq-api-key",
    status_code=status.HTTP_200_OK,
    summary="Define ou atualiza a chave da API da Groq",
    response_model=dict,
)
async def update_groq_api_key(
    payload: GroqApiKeyUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    """
    Salva e criptografa a chave da API da Groq no banco de dados.
    Esta chave é necessária para que as tarefas de transcrição funcionem.
    Requer autenticação.
    """
    await crud.create_or_update_setting(db, key="GROQ_API_KEY", value=payload.api_key)
    return {"message": "Chave da API da Groq foi salva e criptografada com sucesso."}