# EdgeAI - Multi-Agent RAG Platform

Enterprise-grade **Edge-Cloud Hybrid** platform for intelligent document processing with **RAG (Retrieval Augmented Generation)** and **Multi-Agent AI** orchestration.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         EDGE LAYER (Rust)                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐ │
│  │  Edge Collector │  │  Log Buffer     │  │  Batch Streaming    │ │
│  │  (Low Latency)  │──│  (Tokio MPSC)   │──│  (HTTP/TLS)         │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘ │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API (Aauthenticated)
┌──────────────────────────────▼──────────────────────────────────────┐
│                        CLOUD LAYER (Python)                         │
│  ┌──────────────┐  ┌───────────────┐  ┌───────────────────────────┐ │
│  │  FastAPI     │  │  Multi-Agent  │  │  Document Processing      │ │
│  │  Gateway     │──│  Orchestrator │──│  Pipeline (Docling/OCR)   │ │
│  └──────────────┘  └───────────────┘  └───────────────────────────┘ │
│         │                  │                       │                │
│  ┌──────▼──────────────────▼───────────────────────▼──────────────┐ │
│  │                    DATA LAYER                                  │ │
│  │  PostgreSQL 16 + pgvector  │  Redis 7 (Cache)  │  File Store   │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

## Features

### Core Capabilities
- **Multi-Agent AI System** - LangGraph, CrewAI, and custom GenAI orchestration
- **RAG Pipeline** - Document ingestion, chunking, vector embeddings, semantic search
- **Edge-Cloud Hybrid** - Rust edge collector for high-throughput log streaming
- **GPU Acceleration** - CUDA support for embeddings and document OCR

### Document Processing
- **Supported Formats**: PDF, DOCX, PPTX, XLSX, TXT, MD, JSON, CSV, HTML, Images (PNG, JPG, TIFF, BMP)
- **Intelligent Parsing**: IBM Docling v2 with OCR fallback, pypdf for fast PDF extraction
- **100MB Upload Limit** - Enterprise-ready file handling

### AI Agents
| Agent | Framework | Purpose |
|-------|-----------|---------|
| **RAGAgent** | LangGraph | Context-aware Q&A with vector search |
| **SummarizerAgent** | CrewAI | Document summarization |
| **SQLGeneratorAgent** | GenAI | Natural language to SQL |
| **DocumentAnalyzerAgent** | Hybrid | Deep document analysis |
| **QueryRouter** | Custom | Intelligent query routing |

### Frontend
- **React 18** + TypeScript + Vite
- **Tailwind CSS** for modern UI
- **Real-time chat** with source references
- **Document management** dashboard
- **Agent monitoring** panel

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, Zustand |
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy (async), Alembic |
| **Edge Runtime** | Rust, Tokio, Axum, Reqwest |
| **AI/ML** | LangChain, CrewAI, LangGraph, PyTorch |
| **Embeddings** | BAAI/bge-small-en-v1.5 (384 dim, CUDA-accelerated) |
| **LLM** | Groq (cloud, free) or Ollama (local) |
| **Database** | PostgreSQL 16 + pgvector |
| **Cache** | Redis 7 |
| **Container** | Docker Compose, Kubernetes-ready |

## Requirements

- **Python 3.11+**
- **Node.js 18+** (for frontend)
- **Rust 1.70+** (for edge-collector)
- **Docker & Docker Compose**
- **NVIDIA GPU + CUDA** (optional, for acceleration)
- **Groq API Key** (free) OR **Ollama** installed locally

## Quick Start

### 1. Clone and Configure

```bash
git clone https://github.com/your-org/edgeai-rag-platform.git
cd edgeai-rag-platform
cp .env.example .env
```

Edit `.env` with your configuration:
```env
GROQ_API_KEY=gsk_your_key_here
SECRET_KEY=your-secure-secret-key
EDGE_COLLECTOR_API_KEY=your-edge-api-key
```

### 2. Start with Docker Compose

```bash
# Start core services (API, PostgreSQL, Redis)
docker-compose up -d

# With local LLM (Ollama)
docker-compose --profile local-llm up -d

# With Edge Collector
docker-compose --profile edge-collector up -d
```

### 3. Run Database Migrations

```bash
# Inside the API container or locally
alembic upgrade head
```

### 4. Access the Platform

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **Prometheus Metrics** | http://localhost:8000/metrics |

## Project Structure

```
edgeai-rag-platform/
├── src/                          # Python backend
│   ├── api/                      # FastAPI endpoints
│   │   └── v1/endpoints/         # REST API routes
│   ├── agents/                   # AI agent implementations
│   │   ├── langgraph_agents.py   # LangGraph-based agents
│   │   ├── crewai_agents.py      # CrewAI multi-agent
│   │   ├── genai_agents.py       # Custom GenAI agents
│   │   └── hybrid_orchestrator.py # Unified orchestration
│   ├── core/                     # Security, logging, exceptions
│   ├── db/                       # Database models & repositories
│   │   ├── models/               # SQLAlchemy models
│   │   └── repositories/         # Data access layer
│   ├── services/                 # Business logic services
│   │   ├── embedding_service.py  # Vector embeddings (GPU)
│   │   └── document_service.py   # Document processing
│   └── schemas/                  # Pydantic schemas
├── edge-collector/               # Rust edge service
│   ├── src/
│   │   ├── main.rs               # Entry point
│   │   ├── buffer.rs             # Log buffering (MPSC)
│   │   ├── client.rs             # HTTP client with retry
│   │   └── config.rs             # Environment config
│   ├── Cargo.toml
│   └── Dockerfile
├── frontend/                     # React frontend
│   ├── src/
│   │   ├── components/           # UI components
│   │   ├── pages/                # Route pages
│   │   ├── hooks/                # Custom React hooks
│   │   └── stores/               # Zustand state
│   ├── package.json
│   └── vite.config.ts
├── alembic/                      # Database migrations
│   └── versions/
├── tests/                        # Test suites
│   ├── unit/
│   └── integration/
├── docker-compose.yml            # Container orchestration
├── Dockerfile                    # API container
└── requirements.txt              # Python dependencies
```

## API Endpoints

### Authentication
```
POST   /api/v1/auth/register     # Register new user
POST   /api/v1/auth/login        # Login (returns JWT)
GET    /api/v1/auth/me           # Current user info
POST   /api/v1/auth/refresh      # Refresh token
```

### Documents
```
POST   /api/v1/documents/upload              # Upload document
GET    /api/v1/documents                     # List documents
GET    /api/v1/documents/{id}                # Get document
DELETE /api/v1/documents/{id}                # Delete document
GET    /api/v1/documents/{id}/chunks         # Get document chunks
POST   /api/v1/documents/{id}/reprocess      # Reprocess document
```

### Queries (RAG)
```
POST   /api/v1/queries/ask       # Ask question (RAG search)
POST   /api/v1/queries/chat      # Chat with context
POST   /api/v1/queries/sql       # Natural language to SQL
```

### Edge Ingestion
```
POST   /api/v1/ingest/logs       # Batch log ingestion (Edge → Cloud)
```

## Development

### Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run locally
uvicorn src.main:app --reload
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Edge Collector (Rust)

```bash
cd edge-collector
cargo build --release
cargo run
```

### Testing

```bash
# Python tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Linting
ruff check src/
black src/
mypy src/
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection | `postgresql+asyncpg://...` |
| `GROQ_API_KEY` | Groq LLM API key | - |
| `LLM_PROVIDER` | `groq` or `ollama` | `groq` |
| `OLLAMA_BASE_URL` | Ollama endpoint | `http://localhost:11434` |
| `EMBEDDING_MODEL` | HuggingFace model | `BAAI/bge-small-en-v1.5` |
| `MAX_UPLOAD_SIZE_MB` | Max file size | `100` |
| `EDGE_COLLECTOR_API_KEY` | Edge auth key | - |
| `REDIS_ENABLED` | Enable Redis cache | `false` |

### GPU Acceleration

The platform automatically detects NVIDIA GPUs for:
- **Embedding generation** (sentence-transformers)
- **Document OCR** (Docling with CUDA)

Ensure `nvidia-docker` is installed and configured:
```bash
# Verify GPU access
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

## Edge-Cloud Pipeline

The Rust edge collector streams logs to the Python backend:

1. **Edge devices** generate logs/telemetry
2. **Rust collector** buffers in memory (configurable batch size)
3. **Batch flush** on size threshold or time interval
4. **HTTP/TLS** authenticated POST to `/api/v1/ingest/logs`
5. **Python API** writes to PostgreSQL (partitioned table)

### Edge Collector Config

```env
EDGE_COLLECTOR_API_URL=http://api:8000
EDGE_COLLECTOR_BATCH_SIZE=100
EDGE_COLLECTOR_FLUSH_INTERVAL_SECS=5
EDGE_COLLECTOR_API_KEY=your-secret-key
```

## Cost

**$0/month** for core functionality:

| Component | Cost |
|-----------|------|
| **LLM** | Groq free tier (6000 req/day) or Ollama (local) |
| **Embeddings** | HuggingFace (local, GPU-accelerated) |
| **Vector DB** | PostgreSQL + pgvector (self-hosted) |
| **Cache** | Redis (self-hosted) |

## Roadmap

- [ ] Kubernetes Helm charts
- [ ] Prometheus/Grafana monitoring stack
- [ ] WebSocket real-time updates
- [ ] Multi-tenant support
- [ ] S3/GCS storage backend
- [ ] CI/CD pipeline templates

## License

MIT License
