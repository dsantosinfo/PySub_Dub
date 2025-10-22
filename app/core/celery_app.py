# app/core/celery_app.py

import os

# --- CORREÇÃO CRÍTICA ---
# O patch só deve ser aplicado no processo do worker gevent.
# A API FastAPI/Uvicorn (baseada em asyncio) entraria em conflito com o gevent.
# Usamos uma variável de ambiente para aplicar o patch condicionalmente.
if os.environ.get("WORKER_TYPE") == "gevent":
    try:
        from gevent import monkey
        monkey.patch_all()
        import asyncio
        asyncio.set_event_loop_policy(None)
    except (ImportError, AttributeError):
        pass
# --- FIM DA CORREÇÃO ---


# As demais importações agora são seguras em ambos os contextos (api e worker)
import socket
from celery import Celery
from celery.signals import worker_process_init
from app import database
from app.core.config import settings


@worker_process_init.connect
def on_worker_process_init(**kwargs):
    print("Resetando pools de conexão de banco de dados para o novo processo worker...")
    database.dispose_engine_and_session()
    print("Pools de conexão resetados com sucesso.")


# Criação da Instância do Celery
celery_app = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"]
)

# Configuração da Fila Única
celery_app.conf.task_queues = {
    'default_gevent_queue': {'exchange': 'default', 'routing_key': 'default'},
}
celery_app.conf.task_default_queue = 'default_gevent_queue'


# Configuração Adicional do Celery (o restante do arquivo permanece igual)
celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        'health_check_interval': 30,
        'socket_keepalive': True,
        'socket_keepalive_options': {
            socket.TCP_KEEPIDLE: 60,
            socket.TCP_KEEPINTVL: 10,
            socket.TCP_KEEPCNT: 3
        }
    }
)

if __name__ == "__main__":
    celery_app.start()