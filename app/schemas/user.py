# app/schemas/user.py
from pydantic import BaseModel, EmailStr, Field
import uuid
from datetime import datetime

# --- Schemas para ApiKey ---
class ApiKey(BaseModel):
    prefix: str
    created_at: datetime
    last_used_at: datetime | None = None

    class Config:
        from_attributes = True

# --- NOVO: Schema para a resposta do login ---
class ApiKeyResponse(BaseModel):
    """Schema para retornar a chave de API recém-criada ao usuário."""
    api_key: str = Field(..., description="A sua nova chave de API. Guarde-a em um local seguro.")


# --- Schemas para User ---
class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

# --- NOVO: Schema para o corpo da requisição de login ---
class UserLogin(BaseModel):
    """Schema para o payload de login do usuário."""
    email: EmailStr
    password: str


class User(UserBase):
    id: uuid.UUID
    is_active: bool
    api_keys: list[ApiKey] = []

    class Config:
        from_attributes = True