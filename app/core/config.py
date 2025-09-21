# app/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import validator
from functools import lru_cache

class Settings(BaseSettings):
    """
    Classe para gerenciar as configurações da aplicação.

    Carrega as variáveis de ambiente de um arquivo .env e as valida
    usando Pydantic. Isso garante que todas as configurações necessárias
    estejam presentes e corretamente formatadas no início da execução.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # --- Configuração do Banco de Dados ---
    DATABASE_URL: str

    # --- Configuração de Segurança ---
    ENCRYPTION_KEY: str

    # --- Configuração do Broker (Redis) para o Celery ---
    REDIS_URL: str

    # --- Configuração de Diretórios ---
    SHARED_FILES_DIR: str
    TEMP_DIR: str | None = None
    
    # NOTA: A GROQ_API_KEY foi removida daqui, pois agora é gerenciada
    # através da tabela 'settings' no banco de dados.

    @validator("DATABASE_URL")
    def validate_db_url(cls, v: str) -> str:
        """Valida se a URL do banco de dados usa o driver asyncpg."""
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "A DATABASE_URL deve usar o driver 'postgresql+asyncpg://'"
            )
        return v

    @validator("ENCRYPTION_KEY")
    def validate_encryption_key(cls, v: str) -> str:
        """Valida se a chave de criptografia não está vazia."""
        if not v:
            raise ValueError("A ENCRYPTION_KEY não pode ser vazia.")
        return v

@lru_cache
def get_settings() -> Settings:
    """
    Retorna uma instância singleton da classe Settings.

    O uso de @lru_cache garante que a classe Settings seja instanciada
    apenas uma vez, e as mesmas configurações sejam reutilizadas em
    toda a aplicação, otimizando a performance ao evitar a releitura
    do arquivo .env a cada chamada.
    """
    return Settings()

# Instância global das configurações para fácil acesso
settings = get_settings()