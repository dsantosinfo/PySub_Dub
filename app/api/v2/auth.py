# app/api/v2/auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db_session
from app.security import verify_password
from app.schemas.user import UserLogin, ApiKeyResponse

router = APIRouter(prefix="/auth", tags=["V2 - Authentication"])


@router.post(
    "/login",
    response_model=ApiKeyResponse,
    summary="Autentica o usuário e retorna uma nova chave de API",
)
async def login_for_api_key(
    payload: UserLogin, db: AsyncSession = Depends(get_db_session)
):
    """
    Autentica um usuário com e-mail e senha.

    - Se as credenciais forem válidas, todas as chaves de API antigas do usuário
      são revogadas e uma **nova chave de API** é gerada e retornada.
    - Se as credenciais forem inválidas, retorna um erro 401.
    """
    user = await crud.get_user_by_email(db, email=payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou senha incorretos.",
        )

    # Invalida chaves antigas e cria uma nova
    new_api_key, _ = await crud.reset_and_create_api_key_for_user(db, user=user)
    return ApiKeyResponse(api_key=new_api_key)