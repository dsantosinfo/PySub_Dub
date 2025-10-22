# app/database_sync.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Cria a engine de banco de dados SÍNCRONA, usando o driver psycopg2.
# Esta engine é para uso exclusivo do worker gevent (narração).
engine = create_engine(
    settings.DATABASE_SYNC_URL,
    pool_pre_ping=True,
    # Aumenta o pool de conexões para o worker gevent de alta concorrência
    pool_size=10,
    max_overflow=20,
)

# Cria uma fábrica de sessões SÍNCRONAS.
# Cada chamada a SessionLocalSync() criará uma nova sessão de DB.
SessionLocalSync = sessionmaker(autocommit=False, autoflush=False, bind=engine)