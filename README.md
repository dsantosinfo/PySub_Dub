# PySub_Dub: API de Transcrição de Vídeo

PySub_Dub é uma API de alta performance, robusta e escalável construída com FastAPI para transcrever arquivos de vídeo de forma assíncrona. A solução é totalmente containerizada com Docker, utiliza PostgreSQL para persistência de dados, Celery com Redis para processamento em background, e um sistema de autenticação baseado em chaves de API por usuário.

## ✨ Principais Funcionalidades

* **Processamento 100% Assíncrono**: A API permanece responsiva, independentemente do tamanho do vídeo, graças ao Celery.
* **Arquitetura Multi-usuário**: Sistema completo de usuários e chaves de API, permitindo que cada usuário opere de forma isolada e segura.
* **Armazenamento Seguro de Segredos**: A chave da API da Groq é armazenada de forma criptografada no banco de dados.
* **Containerizado com Docker**: Instalação e deploy simplificados com `docker-compose`. A aplicação e seus serviços (PostgreSQL, Redis) rodam em contêineres isolados.
* **Persistência de Dados com PostgreSQL**: Todos os jobs, usuários e configurações são armazenados em um banco de dados relacional, garantindo a integridade e o histórico dos dados.
* **Migrações de Banco de Dados**: O schema do banco é gerenciado com Alembic, facilitando a evolução e manutenção da base de dados.
* **Otimização de Áudio e Divisão Inteligente**: O áudio é extraído, otimizado e dividido de forma inteligente em pontos de silêncio para garantir transcrições de alta qualidade em vídeos longos.
* **Documentação Automática da API**: Interface interativa do Swagger UI (`/docs`) e ReDoc (`/redoc`) gerada automaticamente pelo FastAPI.
* **CLI de Administração**: Um script de linha de comando para tarefas administrativas, como a criação do primeiro usuário.

## 🏗️ Arquitetura e Fluxo de Trabalho

A aplicação utiliza uma arquitetura moderna e desacoplada para garantir escalabilidade e manutenibilidade.

1.  **Criação de Usuário (CLI)**: Um administrador cria o primeiro usuário através de um comando no contêiner da API.
2.  **Login e Autenticação**: O usuário envia suas credenciais (`email`, `senha`) para o endpoint `POST /api/v1/auth/login`. A API valida, invalida chaves antigas e retorna uma nova **chave de API (`X-API-Key`)**.
3.  **Configuração da Groq API Key**: Usando sua `X-API-Key` para autenticação, o usuário configura a chave da API da Groq através do endpoint `PUT /api/v1/settings/groq-api-key`. A chave é criptografada antes de ser salva no banco de dados.
4.  **Submissão do Job**: O usuário envia um arquivo de vídeo para `POST /api/v1/jobs`. A API valida o request, salva o arquivo, cria um registro do job no PostgreSQL com status `PENDING` e enfileira uma tarefa no Celery.
5.  **Processamento em Background (Worker)**:
    * Um worker Celery consome a tarefa da fila do Redis.
    * O status do job no banco é atualizado para `PREPARING`.
    * O worker extrai, otimiza e divide o áudio do vídeo.
    * O status é atualizado para `PROCESSING`.
    * Cada parte do áudio é enviada para a API da Groq para transcrição.
    * Os resultados em formato SRT são combinados e os timestamps são ajustados.
    * O arquivo `.srt` final é salvo, e o status do job é atualizado para `COMPLETED` (ou `FAILED` em caso de erro).
6.  **Consulta de Status e Download**: O usuário pode consultar o andamento em `GET /api/v1/jobs/{job_id}` e, ao concluir, baixar o resultado em `GET /api/v1/jobs/{job_id}/download`.

## 🚀 Começando

A aplicação é projetada para rodar com Docker e Docker Compose, simplificando a configuração do ambiente de desenvolvimento e produção.

### Pré-requisitos

* [Docker](https://www.docker.com/get-started)
* [Docker Compose](https://docs.docker.com/compose/install/)

### Guia de Instalação

1.  **Clone o repositório:**
    ```bash
    git clone <url-do-repositorio>
    cd PySub_Dub
    ```

2.  **Configure as variáveis de ambiente:**
    Copie o arquivo de exemplo e gere uma chave de criptografia segura.
    ```bash
    cp .env.example .env
    ```
    Execute o comando abaixo e cole o resultado na variável `ENCRYPTION_KEY` dentro do arquivo `.env`.
    ```bash
    openssl rand -hex 32
    ```
    O seu `.env` deve parecer com isto:
    ```ini
    # .env
    DATABASE_URL="postgresql+asyncpg://user:password@db:5432/pysub_dub_db"
    ENCRYPTION_KEY="sua_chave_de_64_caracteres_hex_gerada_aqui"
    REDIS_URL="redis://redis:6379/0"
    CELERY_WORKER_CONCURRENCY=4
    SHARED_FILES_DIR="/app/shared_files"
    ```

3.  **Suba os contêineres:**
    Este comando irá construir as imagens, baixar as dependências, iniciar os serviços (API, worker, PostgreSQL, Redis) e aplicar as migrações do banco de dados automaticamente.
    ```bash
    docker-compose up --build -d
    ```

A API estará disponível em `http://localhost:8000`.

## 📖 Como Usar a API

Siga estes passos para começar a transcrever vídeos.

### Passo 1: Criar o Primeiro Usuário (via CLI)

Execute o comando no seu terminal para acessar o contêiner da API e criar um usuário. Substitua o email e a senha.

```bash
docker-compose exec api python run.py create-user admin@example.com SuaSenhaForte123
```

Você verá uma mensagem de sucesso com a sua primeira chave de API. **Guarde esta chave, mas vamos gerar uma nova no próximo passo, que é a prática recomendada.**

### Passo 2: Fazer Login para Obter uma Chave de API

Use o email e a senha definidos para fazer login. Este endpoint sempre invalida chaves antigas e retorna uma nova.

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
-H "Content-Type: application/json" \
-d '{
  "email": "admin@example.com",
  "password": "SuaSenhaForte123"
}'
```

**Resposta Esperada:**

```json
{
  "api_key": "sk_prefixoEchaveSuperSecretaGerada..."
}
```

**Copie o valor de `api_key`. Você irá usá-lo no cabeçalho `X-API-Key` em todas as requisições futuras.**

### Passo 3: Configurar a Chave da API da Groq

Use a chave obtida no passo anterior para se autenticar e salvar sua chave da API da Groq.

```bash
curl -X PUT "http://localhost:8000/api/v1/settings/groq-api-key" \
-H "Content-Type: application/json" \
-H "X-API-Key: sk_sua_chave_de_api_aqui" \
-d '{
  "api_key": "gsk_sua_chave_da_api_da_groq_aqui"
}'
```

### Passo 4: Enviar um Vídeo para Transcrição

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/" \
-H "accept: application/json" \
-H "X-API-Key: sk_sua_chave_de_api_aqui" \
-H "Content-Type: multipart/form-data" \
-F "file=@/caminho/para/seu/video.mp4"
```

**Resposta Esperada (HTTP 202 Accepted):**

```json
{
  "id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
  "user_id": "...",
  "status": "PENDING",
  "original_video_filename": "video.mp4",
  "priority": 5,
  "callback_url": null,
  "error_details": null,
  "retry_count": 0,
  "audio_duration_seconds": null,
  "result_srt_path": null,
  "created_at": "2025-09-21T18:00:00.000Z",
  "updated_at": "2025-09-21T18:00:00.000Z",
  "processing_started_at": null,
  "processing_ended_at": null
}
```

### Passo 5: Verificar o Status do Job

Use o `id` retornado no passo anterior.

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef" \
-H "X-API-Key: sk_sua_chave_de_api_aqui"
```

### Passo 6: Baixar o Arquivo de Legenda (.srt)

Após o status do job mudar para `COMPLETED`:

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/a1b2c3d4-e5f6-7890-1234-567890abcdef/download" \
-H "X-API-Key: sk_sua_chave_de_api_aqui" \
-o legenda_final.srt
```

O comando acima salvará o resultado no arquivo `legenda_final.srt`.

## 🗂️ Estrutura do Projeto

```
PySub_Dub/
├── .dockerignore
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── README.md
├── alembic.ini
├── docker-compose.yml
├── docker-entrypoint.sh
├── requirements.in
├── requirements.txt
├── run.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0_initial_schema.py
├── app/
│   ├── crud.py                 # Funções de interação com o banco (CRUD)
│   ├── database.py             # Configuração da sessão do banco de dados
│   ├── main.py                 # Ponto de entrada da aplicação FastAPI e roteadores
│   ├── security.py             # Funções de autenticação e hashing
│   ├── tasks.py                # Tarefas assíncronas do Celery
│   ├── api/
│   │   └── endpoints.py        # Definição dos endpoints da API
│   ├── core/
│   │   ├── celery_app.py       # Configuração da instância do Celery
│   │   ├── config.py           # Gerenciamento de configurações (variáveis de ambiente)
│   │   └── encryption.py       # Lógica de criptografia para segredos
│   ├── models/                 # Modelos de dados do SQLAlchemy (tabelas)
│   │   ├── base.py
│   │   ├── job.py
│   │   ├── settings.py
│   │   └── user.py
│   ├── schemas/                # Modelos de dados Pydantic (validação e serialização)
│   │   ├── job.py
│   │   ├── settings.py
│   │   └── user.py
│   └── services/
│       └── transcription_service.py # Lógica de negócio principal (extração, transcrição)
└── shared_files/                   # Volume compartilhado para uploads e resultados
```

## 🗄️ Migrações de Banco de Dados (Alembic)

As migrações são aplicadas automaticamente quando o contêiner da API é iniciado. Para criar uma nova migração após alterar os modelos em `app/models/`:

1.  **Gerar o arquivo de migração:**

    ```bash
    docker-compose exec api python -m alembic revision --autogenerate -m "Breve descrição da mudança"
    ```

2.  **Aplicar a nova migração (opcional, pois é automático na inicialização):**

    ```bash
    docker-compose exec api python -m alembic upgrade head
    ```

## 👨‍💻 Desenvolvedor

**DSantos Info**
- 📧 Email: daniel@dsantosinfo.com.br
- 📱 WhatsApp: +55 (21) 99053-2437

---

<div align="center">
  <p><strong>© 2025 DSantos Info. Todos os direitos reservados.</strong></p>
</div>