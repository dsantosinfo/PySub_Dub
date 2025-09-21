# app/models/settings.py

from datetime import datetime
from sqlalchemy import String, Text, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

class Settings(Base):
    """
    Modelo para a tabela 'settings'.
    
    Armazena configurações globais da aplicação em um formato chave-valor.
    Isso permite que configurações, como chaves de API externas, sejam
    gerenciadas através do banco de dados.
    """
    __tablename__ = "settings"

    # A chave de identificação da configuração (ex: "GROQ_API_KEY").
    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    
    # O valor da configuração. Para segredos, este valor deve ser armazenado
    # de forma criptografada. Usamos Text para acomodar valores longos.
    value: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        # Evitamos exibir o valor por segurança
        return f"<Settings(key='{self.key}')>"