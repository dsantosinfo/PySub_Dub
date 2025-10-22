# PySub_Dub

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.118.0-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> API completa para transcrição automática, síntese de voz (TTS) e dublagem de vídeos em português brasileiro.

## 📋 Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Características](#características)
- [Tecnologias](#tecnologias)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Endpoints da API](#endpoints-da-api)
- [Arquitetura](#arquitetura)
- [Desenvolvedor](#desenvolvedor)

## 🎯 Sobre o Projeto

PySub_Dub é uma solução completa para processamento automatizado de mídia, oferecendo:

- **Transcrição automática** de vídeos e áudios usando a API Groq (Whisper Large v3)
- **Síntese de voz (TTS)** com múltiplas vozes em português brasileiro
- **Dublagem automática** de vídeos com narração sincronizada
- **Pipeline assíncrono** para processamento em segundo plano
- **API RESTful** moderna e documentada

## ✨ Características

### Transcrição
- Suporte para vídeos (MP4, AVI, MOV) e áudios (MP3)
- Geração automática de legendas no formato SRT
- Divisão inteligente de arquivos grandes
- Detecção de silêncio para segmentação precisa

### Narração e TTS
- **10 vozes locais** via Piper TTS (offline):
  - `cadu`, `edresson`, `faber`, `jeff`
- **16 vozes em nuvem** via Microsoft Edge TTS:
  - `br-antonio`, `br-brenda`, `br-donato`, `br-elza`, `br-fabio`, `br-francisca`
  - `br-giovanna`, `br-humberto`, `br-julio`, `br-leila`, `br-leticia`, `br-manuela`
  - `br-nicolau`, `br-thalita`, `br-valerio`, `br-yara`
- Síntese adaptativa com sincronização temporal
- Ajuste automático de velocidade e pausas

### Dublagem
- União automática de áudio narrado com vídeo original
- Preservação da qualidade do vídeo (cópia sem re-codificação)
- Sincronização precisa baseada em timestamps SRT

## 🛠 Tecnologias

### Backend
- **FastAPI** - Framework web moderno e assíncrono
- **SQLAlchemy** - ORM com suporte async
- **Alembic** - Migrações de banco de dados
- **Celery + Gevent** - Processamento assíncrono de tarefas
- **Redis** - Broker de mensagens e cache
- **PostgreSQL** - Banco de dados relacional

### Processamento de Mídia
- **FFmpeg** - Manipulação de vídeo e áudio
- **Librosa** - Análise de áudio
- **Pydub** - Edição de áudio
- **Piper TTS** - Síntese de voz local (ONNX)
- **Edge TTS** - Síntese de voz em nuvem (Microsoft)

### IA e Transcrição
- **Groq API** - Transcrição via Whisper Large v3
- **ONNX Runtime** - Inferência de modelos de ML

## 📦 Pré-requisitos

- Docker 20.10+
- Docker Compose 2.0+
- Python 3.12+ (para desenvolvimento local)
- FFmpeg (instalado via Docker)

## 🚀 Instalação

### Usando Docker (Recomendado)

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/pysub-dub.git
cd pysub-dub
```

2. Configure as variáveis de ambiente:
```bash
cp .env.exemple .env
# Edite o arquivo .env com suas configurações
```

3. Inicie os serviços:
```bash
docker-compose up -d
```

4. Execute as migrações do banco:
```bash
docker-compose exec api python -m alembic upgrade head
```

5. Crie um usuário administrador:
```bash
docker-compose exec api python create_user.py admin@exemplo.com SuaSenha123
```

A API estará disponível em: `http://localhost:8000`

### Desenvolvimento Local

1. Crie um ambiente virtual:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate  # Windows
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Configure o `.env` apontando para localhost:
```bash
cp .env.exemple .env
# Ajuste DATABASE_URL e REDIS_URL para localhost
```

4. Execute as migrações:
```bash
alembic upgrade head
```

5. Inicie a API:
```bash
python run.py
```

6. Em outro terminal, inicie o worker:
```bash
celery -A app.core.celery_app.celery_app worker --loglevel=info -P gevent -c 50
```

## ⚙️ Configuração

### Variáveis de Ambiente

Edite o arquivo `.env` com suas configurações:

```bash
# Banco de Dados
DATABASE_URL="postgresql+asyncpg://user:password@localhost:5432/pysub_dub_db"
DATABASE_SYNC_URL="postgresql+psycopg2://user:password@localhost:5432/pysub_dub_db"

# Segurança
ENCRYPTION_KEY="sua-chave-base64-aqui"  # Gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Redis
REDIS_URL="redis://localhost:6379/0"

# Diretórios
SHARED_FILES_DIR="shared_files_local"

# Worker
CELERY_WORKER_CONCURRENCY=4
```

### Configuração da API Groq

A chave da API da Groq deve ser configurada via endpoint da API:

```bash
curl -X PUT http://localhost:8000/api/v2/settings/groq-api-key \
  -H "X-API-Key: sua-chave-api" \
  -H "Content-Type: application/json" \
  -d '{"api_key": "gsk_..."}'
```

Obtenha sua chave em: https://console.groq.com/keys

## 📚 Uso

### 1. Autenticação

Faça login para obter uma chave de API:

```bash
curl -X POST http://localhost:8000/api/v2/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@exemplo.com",
    "password": "SuaSenha123"
  }'
```

Resposta:
```json
{
  "api_key": "sk_abc123..."
}
```

Use esta chave no header `X-API-Key` em todas as requisições.

### 2. Transcrição de Vídeo

```bash
curl -X POST http://localhost:8000/api/v2/transcriptions/ \
  -H "X-API-Key: sk_abc123..." \
  -F "file=@video.mp4" \
  -F "priority=5"
```

Resposta:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "PENDING",
  "media_type": "video",
  ...
}
```

### 3. Consultar Status da Transcrição

```bash
curl -X GET http://localhost:8000/api/v2/transcriptions/550e8400-e29b-41d4-a716-446655440000 \
  -H "X-API-Key: sk_abc123..."
```

### 4. Baixar Arquivo SRT

```bash
curl -X GET http://localhost:8000/api/v2/transcriptions/550e8400-e29b-41d4-a716-446655440000/srt \
  -H "X-API-Key: sk_abc123..." \
  -o resultado.srt
```

### 5. Criar Narração a partir da Transcrição

```bash
curl -X POST http://localhost:8000/api/v2/transcriptions/550e8400-e29b-41d4-a716-446655440000/narrate \
  -H "X-API-Key: sk_abc123..." \
  -H "Content-Type: application/json" \
  -d '{"voice": "br-antonio"}'
```

### 6. Unir Narração com Vídeo (Dublagem)

```bash
curl -X POST http://localhost:8000/api/v2/narrations/{narration_id}/merge \
  -H "X-API-Key: sk_abc123..."
```

### 7. Baixar Vídeo Dublado

```bash
curl -X GET http://localhost:8000/api/v2/narrations/{narration_id}/video \
  -H "X-API-Key: sk_abc123..." \
  -o video_dublado.mp4
```

### 8. TTS Direto (Texto para Áudio)

```bash
curl -X POST http://localhost:8000/api/v2/narrations/text-to-speech \
  -H "X-API-Key: sk_abc123..." \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Olá, este é um teste de síntese de voz.",
    "voice": "br-francisca"
  }'
```

## 🔌 Endpoints da API

### Autenticação
- `POST /api/v2/auth/login` - Autenticar e obter chave de API

### Configurações
- `PUT /api/v2/settings/groq-api-key` - Configurar chave da API Groq

### Transcrições
- `POST /api/v2/transcriptions/` - Criar nova transcrição
- `GET /api/v2/transcriptions/` - Listar transcrições
- `GET /api/v2/transcriptions/{id}` - Consultar transcrição
- `GET /api/v2/transcriptions/{id}/srt` - Baixar arquivo SRT
- `POST /api/v2/transcriptions/{id}/cancel` - Cancelar transcrição
- `POST /api/v2/transcriptions/{id}/retry` - Tentar novamente
- `DELETE /api/v2/transcriptions/{id}` - Deletar transcrição
- `POST /api/v2/transcriptions/{id}/narrate` - Criar narração

### Narrações
- `GET /api/v2/narrations/voices` - Listar vozes disponíveis
- `POST /api/v2/narrations/text-to-speech` - TTS direto
- `GET /api/v2/narrations/{id}` - Consultar narração
- `GET /api/v2/narrations/{id}/audio` - Baixar áudio MP3
- `GET /api/v2/narrations/{id}/merge` - Status do merge
- `POST /api/v2/narrations/{id}/merge` - Iniciar merge com vídeo
- `GET /api/v2/narrations/{id}/video` - Baixar vídeo dublado
- `POST /api/v2/narrations/{id}/cancel` - Cancelar narração
- `POST /api/v2/narrations/{id}/retry` - Tentar novamente

Documentação completa: `http://localhost:8000/docs`

## 🏗 Arquitetura

```
┌─────────────┐
│   Cliente   │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────┐
│          FastAPI (API)              │
│  ┌─────────────────────────────┐   │
│  │    Endpoints RESTful        │   │
│  │  - Auth                     │   │
│  │  - Transcriptions           │   │
│  │  - Narrations               │   │
│  │  - Settings                 │   │
│  └──────────┬──────────────────┘   │
└─────────────┼───────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│         PostgreSQL                  │
│  - Users & API Keys                 │
│  - Jobs (Transcriptions)            │
│  - Narrations                       │
│  - Settings                         │
└─────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────┐
│      Redis (Message Broker)         │
└──────────┬──────────────────────────┘
           │
           ▼
┌─────────────────────────────────────┐
│    Celery Workers (Gevent Pool)     │
│  ┌──────────────────────────────┐  │
│  │  Transcrição Pipeline        │  │
│  │  - Extração de áudio         │  │
│  │  - Divisão em chunks         │  │
│  │  - API Groq (Whisper)        │  │
│  │  - Combinação de SRTs        │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Narração Pipeline           │  │
│  │  - Análise de SRT            │  │
│  │  - TTS (Piper/Edge)          │  │
│  │  - Sincronização temporal    │  │
│  └──────────────────────────────┘  │
│  ┌──────────────────────────────┐  │
│  │  Merge Pipeline              │  │
│  │  - FFmpeg merge              │  │
│  │  - Vídeo final               │  │
│  └──────────────────────────────┘  │
└─────────────────────────────────────┘
```

### Fluxo de Processamento

1. **Upload**: Cliente envia vídeo/áudio via API
2. **Enfileiramento**: Tarefa é criada no Redis
3. **Processamento**: Worker Celery executa pipeline
4. **Persistência**: Resultados salvos em disco e DB
5. **Notificação**: Status atualizado (polling ou webhook)
6. **Download**: Cliente baixa resultados (SRT/MP3/MP4)

## 👨‍💻 Desenvolvedor

**Daniel Santos**  
DSantosInfo

- 📧 Email: contato@dsantosinfo.com.br
- 🌐 Website: [dsantosinfo.com.br](https://dsantosinfo.com.br)

---

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

## 🤝 Contribuindo

Contribuições são bem-vindas! Sinta-se à vontade para abrir issues ou pull requests.

1. Fork o projeto
2. Crie sua branch (`git checkout -b feature/MinhaFeature`)
3. Commit suas mudanças (`git commit -m 'Adiciona MinhaFeature'`)
4. Push para a branch (`git push origin feature/MinhaFeature`)
5. Abra um Pull Request

## 📝 Changelog

### v2.0.0 (2025-10-22)
- ✨ Adição de suporte para arquivos de áudio MP3
- ✨ Integração com Microsoft Edge TTS (16 vozes em nuvem)
- ✨ Pipeline de dublagem (merge de vídeo + narração)
- ♻️ Refatoração completa para arquitetura modular
- 🐛 Correções diversas de estabilidade

### v1.0.0 (2025-09-21)
- 🎉 Release inicial
- ✨ Transcrição de vídeos
- ✨ TTS com Piper (4 vozes locais)
- ✨ API RESTful com autenticação

---

⭐ Se este projeto foi útil para você, considere dar uma estrela no repositório!