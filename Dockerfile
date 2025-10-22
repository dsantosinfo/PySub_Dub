# Dockerfile

# --- Estágio 1: Base ---
FROM python:3.12-slim-bullseye AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ffmpeg \
       dos2unix \
       libgomp1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Estágio 2: Builder de Dependências Python ---
FROM base AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Estágio 3: Imagem Final da Aplicação ---
FROM base
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Cria o grupo e o usuário 'app'
RUN addgroup --system app && adduser --system --group app

# Copia o código da aplicação
COPY . .

# Copia o entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
RUN dos2unix /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# --- MUDANÇA CRÍTICA ---
# Como root, ajustamos a propriedade de todos os arquivos da aplicação
# para o usuário 'app', incluindo a pasta de modelos.
RUN chown -R app:app /app

# Troca permanentemente para o usuário 'app'.
# Todos os comandos subsequentes serão executados como 'app'.
USER app

ENTRYPOINT ["docker-entrypoint.sh"]

EXPOSE 8000