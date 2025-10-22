# app/database.py

import os
from typing import AsyncGenerator, Optional

# --- NOVAS IMPORTAÇÕES ---
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
# --- FIM DAS NOVAS IMPORTAÇÕES ---

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession, AsyncEngine
from app.core.config import settings

_engine: Optional[AsyncEngine] = None
_async_session_local: Optional[async_sessionmaker[AsyncSession]] = None

# --- NOVO: Engine e Session Factory SÍNCRONOS para Gevent ---
_sync_engine = None
_sync_session_local = None

def get_sync_engine():
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_SYNC_URL, pool_pre_ping=True)
    return _sync_engine

def get_sync_session_local():
    global _sync_session_local
    if _sync_session_local is None:
        engine = get_sync_engine()
        _sync_session_local = sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )
    return _sync_session_local
# --- FIM DO NOVO BLOCO ---


def dispose_engine_and_session():
    global _engine, _async_session_local, _sync_engine, _sync_session_local
    _engine = None
    _async_session_local = None
    _sync_engine = None
    _sync_session_local = None

def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(settings.DATABASE_URL, pool_pre_ping=True)
    return _engine

def get_async_session_local() -> async_sessionmaker[AsyncSession]:
    global _async_session_local
    if _async_session_local is None:
        engine = get_engine()
        _async_session_local = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
    return _async_session_local

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async_session_local = get_async_session_local()
    async with async_session_local() as session:
        try:
            yield session
        finally:
            await session.close()