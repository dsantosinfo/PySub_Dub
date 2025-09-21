# app/models/base.py

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid

class Base(DeclarativeBase):
    """
    Classe base para todos os modelos do ORM.
    """
    pass

class BaseUUID(Base):
    """
    Uma classe base abstrata que adiciona uma coluna de ID UUID.
    """
    __abstract__ = True  # Corrigido: Indentação ajustada para dentro da classe
    
    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )