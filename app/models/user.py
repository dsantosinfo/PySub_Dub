# app/models/user.py

import uuid
from datetime import datetime
from typing import List, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, func, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseUUID

if TYPE_CHECKING:
    from .job import Job
    # A importação de ApiKey foi removida, pois a classe está neste mesmo arquivo.

class User(BaseUUID):
    """
    Modelo para a tabela 'users'.
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    api_keys: Mapped[List["ApiKey"]] = relationship(
        "ApiKey", back_populates="user", cascade="all, delete-orphan"
    )
    
    jobs: Mapped[List["Job"]] = relationship(
        "Job", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}')>"


class ApiKey(BaseUUID):
    """
    Modelo para a tabela 'api_keys'.
    """
    __tablename__ = "api_keys"

    hashed_key: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    prefix: Mapped[str] = mapped_column(String(8), unique=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey(id={self.id}, prefix='{self.prefix}', user_id={self.user_id})>"