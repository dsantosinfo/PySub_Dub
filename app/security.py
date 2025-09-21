# app/security.py

import secrets
import hashlib
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.database import get_db_session
from app.models.user import User

# --- Configuração de Hashing de Senha ---
# Usamos passlib com bcrypt, o padrão recomendado para senhas.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

API_KEY_HEADER = "X-API-Key"
api_key_header_scheme = APIKeyHeader(name=API_KEY_HEADER, auto_error=True)

# --- Funções de Senha ---

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Gera o hash de uma senha."""
    return pwd_context.hash(password)

# --- Funções de Chave de API ---

def generate_api_key() -> tuple[str, str]:
    """Gera uma nova chave de API segura e seu prefixo."""
    # Gera uma chave segura e longa
    key = secrets.token_urlsafe(32)
    prefix = key[:8]
    # Retorna a chave completa com um prefixo "sk_" (secret key)
    full_key = f"sk_{prefix}{key}"
    return full_key, prefix

def get_api_key_hash(plain_key: str) -> str:
    """Gera o hash SHA-256 de uma chave de API para armazenamento seguro."""
    # Usamos SHA-256 para chaves de API pois é rápido e determinístico,
    # ideal para buscas no banco.
    return hashlib.sha256(plain_key.encode()).hexdigest()

# --- Dependência de Autenticação do FastAPI ---

async def get_current_user(
    api_key: str = Depends(api_key_header_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """
    Dependência para validar a chave de API e retornar o usuário correspondente.
    
    Será usada para proteger os endpoints da API.
    """
    user = await crud.get_user_by_api_key(db, key=api_key)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API inválida ou usuário inativo",
            headers={"WWW-Authenticate": "Header"},
        )
    return user