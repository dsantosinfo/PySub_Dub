#!/bin/sh
# docker-entrypoint.sh

# Apenas executa o comando passado para o contêiner.
# A troca de usuário e as permissões são gerenciadas pelo Dockerfile.
set -e
exec "$@"