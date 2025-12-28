# EdgeAI - Multi-Agent RAG Platform

Enterprise-grade hybrid edge-cloud platform for document processing with RAG (Retrieval Augmented Generation) and multi-agent AI capabilities.

## 🚀 Features

- **FastAPI REST API Gateway** with JWT authentication
- **Document Ingestion Pipeline**: PDF/Text → chunks → embeddings → pgvector
- **Multi-Agent System**: LangChain + CrewAI orchestration
- **FREE LLM Providers**: Groq (cloud) or Ollama (local)
- **FREE Embeddings**: HuggingFace all-MiniLM-L6-v2 (CPU-based)
- **Vector Database**: PostgreSQL + pgvector

## 📋 Requirements

- Python 3.11+
- Docker & Docker Compose
- Groq API key (free) OR Ollama installed locally

## 🛠️ Quick Start

### 1. Clone and Setup

```bash
cd edgeai-rag-platform
cp .env.example .env
# Edit .env with your configuration
```

### 2. Get Groq API Key (Free)

1. Go to https://console.groq.com/keys
2. Sign up/login and create an API key
3. Add to `.env`: `GROQ_API_KEY=gsk_your_key_here`

### 3. Start with Docker

```bash
docker-compose up -d
```

### 4. Access the API

- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- PgAdmin: http://localhost:5050

## 📁 Project Structure

```
edgeai-rag-platform/
├── src/
│   ├── api/          # FastAPI endpoints
│   ├── core/         # Security, exceptions, logging
│   ├── db/           # Database models & repositories
│   ├── services/     # Business logic
│   ├── agents/       # AI agents (CrewAI)
│   ├── ingestion/    # Document processing pipeline
│   └── utils/        # Utility functions
├── migrations/       # Alembic migrations
├── tests/           # Unit & integration tests
└── docs/            # Documentation
```

## 🤖 Agents

| Agent | Purpose |
|-------|---------|
| **QueryRouter** | Routes queries to appropriate specialist agents |
| **DocumentAnalyzer** | Extracts and analyzes information from documents |
| **Summarizer** | Creates concise document summaries |
| **SQLGenerator** | Converts natural language to SQL queries |

## 💰 Cost

**$0/month** - All components use free tiers:
- LLM: Groq (6000 req/day free) or Ollama (local)
- Embeddings: HuggingFace (local CPU)
- Vector DB: pgvector (self-hosted)

## 📖 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register user
- `POST /api/v1/auth/login` - Login
- `GET /api/v1/auth/me` - Current user

### Documents
- `POST /api/v1/documents/upload` - Upload document
- `GET /api/v1/documents` - List documents
- `GET /api/v1/documents/{id}` - Get document

### Queries
- `POST /api/v1/queries/ask` - Ask question (RAG)
- `POST /api/v1/queries/chat` - Chat with context
- `POST /api/v1/queries/sql` - Natural language to SQL

## 🔧 Development

```bash
# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run tests
pytest

# Run linting
ruff check src/
black src/

# Run locally
uvicorn src.main:app --reload
```

## 📝 License

MIT License