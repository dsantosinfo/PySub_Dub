from celery import Celery
from app.core.config import settings

# --- Criação da Instância do Celery ---
# O primeiro argumento é o nome do módulo atual.
# O 'broker' aponta para o nosso serviço Redis.
# O 'backend' também aponta para o Redis, que será usado para armazenar
# os resultados e o estado das tarefas.
celery_app = Celery(
    "tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"] # Lista de módulos onde o Celery deve procurar por tarefas.
)

# --- Configuração Adicional do Celery ---
# Atualiza a configuração do Celery com configurações adicionais, se necessário.
# Por exemplo, pode-se definir timeouts, serializadores, etc.
celery_app.conf.update(
    task_track_started=True,
    result_expires=3600,  # Os resultados expiram após 1 hora.
    # Adicione outras configurações do Celery aqui.
)

if __name__ == "__main__":
    celery_app.start()
