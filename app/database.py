# app/database.py

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.config import settings

# Cria o 'engine' assíncrono do SQLAlchemy.
# O engine é o ponto de entrada de baixo nível para o banco de dados.
# pool_pre_ping=True verifica a vitalidade das conexões antes de usá-las.
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)

# Cria uma fábrica de sessões assíncronas.
# Esta fábrica será usada para criar novas sessões de banco de dados
# sempre que precisarmos interagir com o banco.
# expire_on_commit=False é recomendado para aplicações assíncronas
# para que os objetos continuem acessíveis após o commit da transação.
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependência do FastAPI para obter uma sessão de banco de dados.

    Este é um gerador assíncrono que irá:
    1. Criar e fornecer uma nova sessão de banco de dados por requisição.
    2. Garantir que a sessão seja sempre fechada ao final da requisição,
       mesmo que ocorram erros.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()