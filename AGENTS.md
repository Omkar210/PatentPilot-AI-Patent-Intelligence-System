# PatentPilot AI — Agent Rules

## Project
AI-powered multi-agent patent intelligence platform. 6-person CDAC team, 4-week
build. Helps users search, compare, and evaluate AI/emerging-tech patents via
a multi-agent pipeline with human approval before final conclusions.

## Locked workflow (11 stages — do not add/remove stages without being asked)
1. User query submitted (FastAPI endpoint)
2. Planner agent — breaks query into search keywords
3. Search agents (parallel) — Patent Search (PatentsView API) + Research Paper
   Search (Semantic Scholar API)
4. Document processing — PyMuPDF for text-based PDFs, PaddleOCR fallback for
   scanned pages
5. Entity extraction — claims, inventors, IPC/CPC codes, algorithms
6. Embedding + vector search — ChromaDB, sentence-transformers embeddings
7. Knowledge graph — Neo4j, relationships between patents/inventors/entities
8. Similarity & prior art agent
9. Novelty assessment agent — explainable score with cited evidence
10. Report generation agent
11. Human approval — approve / reject / request re-analysis

## Tech stack (exact versions — see requirements.txt, do not upgrade without asking)
fastapi 0.116.1, uvicorn 0.35.0, sqlalchemy 2.0.43, psycopg2-binary 2.9.10,
alembic 1.16.5, langgraph 0.6.6, langchain 0.3.27, langchain-community 0.3.29,
langchain-core 0.3.75, chromadb 1.0.20, neo4j 5.28.2, networkx 3.5,
sentence-transformers 5.1.0, pandas 2.3.2, numpy 2.3.2, httpx 0.28.1,
requests 2.32.5, PyMuPDF 1.26.4, paddlepaddle 3.1.1, paddleocr 3.2.0,
opencv-python 4.12.0.88, Pillow 11.3.0, transformers 4.55.4, accelerate 1.10.0

LLM calls go through a hosted API (Groq or Gemini), not a locally-loaded
transformers model — this team has minimum local compute available.
transformers/accelerate are reserved for small, optional local tasks only
(e.g. a lightweight classifier), never for the main generation calls in the
Planner, Entity Extraction, or Novelty Assessment agents.

## Rules
- Don't change the locked workflow scope unless explicitly told to.
- Every new agent goes in /agents as its own file, named after its stage
  (e.g. agents/planner.py, agents/novelty.py).
- Every agent function takes and returns a partial PatentPilotState dict
  (defined in state.py) — never a different shape.
- Use environment variables via python-dotenv for all API keys. Never
  hardcode a key. Always add new required keys to .env.example.
- Prefer hosted API calls over local model loading, given minimum local
  compute.
- After writing code for a stage, write or update a matching test that
  actually calls the function with sample input before marking the task done.
- Use the browser agent to verify FastAPI endpoints respond correctly
  (e.g. hit /docs, confirm the OpenAPI schema renders) before marking API
  tasks complete.
- Commit with clear messages per completed sub-task; don't bundle unrelated
  changes in one commit.
