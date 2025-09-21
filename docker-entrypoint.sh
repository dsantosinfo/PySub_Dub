#!/bin/sh
# docker-entrypoint.sh

# Sai imediatamente se um comando falhar
set -e

# Garante que o usuário 'app' seja o dono do volume compartilhado.
echo "Updating shared_files ownership..."
chown -R app:app /app/shared_files

# Verifica se o comando a ser executado é o da API (python run.py).
if [ "$1" = "python" ] && [ "$2" = "run.py" ]; then
  echo "Container de API detectado. Executando migrações do banco de dados..."
  
  # Executa o alembic como um módulo do Python para evitar problemas de $PATH
  gosu app python -m alembic upgrade head
  
  echo "Migrações do banco de dados concluídas."
fi

# Executa o comando principal do contêiner
exec gosu app "$@"