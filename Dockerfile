# Dockerfile

# --- Estágio 1: Base ---
FROM python:3.12-slim-bullseye AS base

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala dependências, gosu e dos2unix
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsm6 libxext6 gosu dos2unix \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# --- Estágio 2: Builder de Dependências ---
FROM base AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Estágio 3: Imagem Final ---
FROM base
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Cria o usuário não-root
RUN addgroup --system app && adduser --system --group app

# Copia o código da aplicação
COPY . .

# Copia e prepara o entrypoint
COPY docker-entrypoint.sh /usr/local/bin/
# Converte as quebras de linha de Windows (CRLF) para Unix (LF) E torna o script executável
RUN dos2unix /usr/local/bin/docker-entrypoint.sh \
    && chmod +x /usr/local/bin/docker-entrypoint.sh

# Define o entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]

# Expõe a porta
EXPOSE 8000