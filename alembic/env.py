# alembic/env.py

import os
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(".env")
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# Importa a Base declarativa e todos os modelos.
# Isso é VITAL para que o Alembic "enxergue" nossas tabelas e possa
# autogerar as migrações comparando os modelos com o estado do banco.
from app.models.base import Base
from app.models.job import Job
from app.models.user import User, ApiKey
from app.models.settings import Settings
from app.models.narration import Narration  # <<< ADICIONADO


# Carrega a configuração de log do arquivo alembic.ini
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Define o metadado de nossos modelos como o alvo para o Alembic
target_metadata = Base.metadata

# Obtém a URL do banco de dados a partir da variável de ambiente
# definida no alembic.ini e carregada do .env
config.set_main_option(
    "sqlalchemy.url", os.environ.get("DATABASE_URL", "")
)


def run_migrations_offline() -> None:
    """Executa migrações no modo 'offline'.
    Isso gera scripts SQL que podem ser executados manualmente.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Executa migrações no modo 'online'.
    Conecta-se ao banco de dados e aplica as migrações diretamente.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())