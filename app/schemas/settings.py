# app/schemas/settings.py
from pydantic import BaseModel, Field

# --- Schemas Genéricos para a Entidade Setting ---

class Setting(BaseModel):
    key: str
    value: str

    class Config:
        from_attributes = True

class SettingUpdate(BaseModel):
    value: str

# --- Schema Específico para o Endpoint da Chave Groq ---

class GroqApiKeyUpdate(BaseModel):
    """
    Schema para validar o corpo da requisição para atualizar a chave da API da Groq.
    """
    api_key: str = Field(
        ...,
        min_length=10,  # Uma validação mínima para evitar strings vazias
        description="A sua chave de API completa e válida obtida no site da Groq.",
        examples=["gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"]
    )