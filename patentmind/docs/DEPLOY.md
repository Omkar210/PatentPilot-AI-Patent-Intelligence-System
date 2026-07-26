# PatentMind AI — Deployment Guide

## Prerequisites

| Requirement | Version | Purpose |
|------------|---------|----------|
| Python | 3.11+ | Runtime for FastAPI, ML models, batch pipelines |
| Docker + Compose | 20.10+ / v2 | PostgreSQL, Neo4j, optional full-stack container |
| Qdrant Binary | 1.9+ | Vector database (runs as standalone binary, NOT in Docker) |
| Ollama | Latest | Serves Qwen3-4B / Qwen2.5:3b for local LLM inference |
| AWS Credentials | - | S3 access for patent PDF storage |
| Groq API Key | - | Fallback LLM via cloud API |

---

## 1. Environment Setup

```bash
# Clone repository
git clone https://github.com/Omkar210/PatentPilot-AI-Patent-Intelligence-System.git
cd PatentPilot-AI-Patent-Intelligence-System/patentmind

# Create virtual environment
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate
# Activate (Linux/Mac)
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials:
#   DATABASE_URL, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
#   AWS_REGION, S3_BUCKET_NAME, QDRANT_HOST, QDRANT_PORT,
#   NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD,
#   GROQ_API_KEY, OLLAMA_BASE_URL
```

---

## 2. Infrastructure Services

### Option A: Docker Compose (Recommended)

```bash
# Start PostgreSQL + Neo4j
docker-compose up -d postgres neo4j

# Verify services
docker-compose ps
```

### Option B: Manual Setup

```bash
# PostgreSQL
sudo systemctl start postgresql
createdb patentmind_db

# Neo4j (if available)
neo4j start
```

### Qdrant Vector Database

> **Important:** Qdrant runs as a standalone binary, NOT inside Docker.

```bash
# Download and start Qdrant
./qdrant --config-path qdrant_config.yaml &

# Verify (default port 6333)
curl http://localhost:6333/collections
```

### Ollama LLM Service

```bash
# Start Ollama server
ollama serve &

# Pull the model
ollama pull qwen2.5:3b
# or for GPU servers with more VRAM:
ollama pull qwen3:4b

# Verify
curl http://localhost:11434/api/tags
```

---

## 3. Data Pipeline Execution

Run these in sequence. Each stage must complete before the next begins.

```bash
# Stage 1-4: Ingest patents from USPTO, WIPO, Google Patents → S3
python -m patentmind.ingestion.pipeline

# Stage 5-8: Extract text (PyMuPDF + PaddleOCR), clean, enrich
# ⚠ GPU batch job — do NOT run Qwen3-4B simultaneously
python -m patentmind.processing.pipeline

# Stage 9-11: Generate embeddings → store in Qdrant
# ⚠ GPU batch job — sequence after OCR is complete
python -m patentmind.embeddings.pipeline
```

---

## 4. Launch Application

### Quick Start (Recommended)

```bash
# From project root (one level above patentmind/)
python start_all_services.py
```

This script automatically:
- Detects and activates the `.venv` virtual environment
- Initializes the database
- Checks Qdrant, Ollama, Neo4j connectivity
- Launches FastAPI on port 8000

### Manual Launch

```bash
uvicorn patentmind.api.main:app --host 0.0.0.0 --port 8000
```

### Docker Full-Stack

```bash
docker-compose up --build
```

---

## 5. Access

| Interface | URL | Description |
|-----------|-----|-------------|
| Web UI | http://localhost:8000 | PatentMind dashboard |
| API Docs | http://localhost:8000/docs | Swagger/OpenAPI interactive docs |
| Neo4j Browser | http://localhost:7474 | Graph database browser |
| Qdrant Dashboard | http://localhost:6333/dashboard | Vector DB management |

### SSH Port Forwarding (Remote GPU Server)

```bash
ssh -N -L 8000:localhost:8000 gpuuser@192.168.6.50 -p 22
# Then access: http://localhost:8000
```

---

## 6. Running Tests

```bash
# All tests
python -m pytest patentmind/tests/ -v

# E2E integration tests only
python -m pytest patentmind/tests/test_e2e_integration.py -v

# Fallback mechanism tests only
python -m pytest patentmind/tests/test_fallback_mechanisms.py -v
```

---

## 7. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `_regex.pyd` DLL blocked | Windows App Control (WDAC) | System auto-falls back to `DeterministicHashEncoder` — no action needed |
| Neo4j connection refused | Service not running | Start Neo4j or ignore — system uses simulated graph fallback |
| PaddleOCR import error | PaddlePaddle not available for Python 3.11+ | System falls back to PyMuPDF text extraction |
| `numpy` version conflict | opencv/numpy mismatch | Pin `numpy>=1.26.0,<2.3.0` in requirements.txt |
| Ollama timeout on queries | Model loading slow on first call | Wait 30s for model warm-up; system falls back to Groq |
| S3 access denied | Missing/wrong AWS credentials | Check `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    start_all_services.py                     │
│              (auto-venv, health checks, launch)              │
├──────────────┬──────────────┬──────────────┬────────────────┤
│  PostgreSQL  │   Qdrant     │   Ollama     │    Neo4j       │
│  (SQLAlchemy)│ (Vectors)    │ (Qwen3-4B)   │  (Knowledge    │
│              │              │  + Groq ↓    │   Graph)       │
├──────────────┴──────────────┴──────────────┴────────────────┤
│                    FastAPI Backend                           │
│    /api/query  /api/patents  /api/compare-pdf  /api/stats   │
├─────────────────────────────────────────────────────────────┤
│                  Frontend UI (Static HTML)                   │
│          Earth-tone theme · 5 screens · Live API             │
└─────────────────────────────────────────────────────────────┘
```
