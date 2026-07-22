# Project: PatentPilot AI — Data Ingestion Pipeline

## Architecture
The Data Ingestion pipeline comprises Stages 1–4 of the 11-stage PatentPilot AI LangGraph pipeline:
1. `user_query`: Input node receiving query string.
2. `planner`: LLM agent generating 3–6 search keywords as JSON.
3. `search`: Concurrent fetch node querying PatentsView and Semantic Scholar via `asyncio.gather`.
4. `document_processing`: Text extraction node processing PDFs (PyMuPDF `fitz`) with OCR fallback (PaddleOCR/RapidOCR) or abstract text.

Data flows through `PatentPilotState` (defined in `state.py`).

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | API Clients | `ingestion/patentsview.py`, `ingestion/semantic_scholar.py` | None | DONE |
| M2 | Planner Agent | `agents/planner.py` | None | DONE |
| M3 | Search Agent Node | `agents/search.py` | M1 | DONE |
| M4 | Document Processing Node | `agents/document_processing.py`, `ingestion/ocr_fallback.py` | None | DONE |
| M5 | Workflow Wiring & E2E Verification | `graph.py`, test script | M1, M2, M3, M4 | DONE |

## Interface Contracts

### M1: API Clients
- `ingestion/patentsview.py`: `async def search_patents(keywords: List[str], max_results: int = 10) -> List[Dict[str, Any]]`
  - Output fields per patent: `patent_id`, `title`, `abstract`, `inventors`, `ipc_codes`, `pdf_url`
- `ingestion/semantic_scholar.py`: `async def search_papers(keywords: List[str], max_results: int = 10) -> List[Dict[str, Any]]`
  - Output fields per paper: `paper_id`, `title`, `abstract`, `url`, `year`, `authors`

### M2: Planner Agent
- `agents/planner.py`: `def planner_agent_node(state: PatentPilotState) -> Dict[str, Any]`
  - Inputs: `state["user_query"]`
  - Outputs: `{"search_keywords": List[str]}` (3-6 strings)
  - Uses hosted LLM API (Google Gemini 2.5 Flash / Groq fallback, temp=0)

### M3: Search Agent Node
- `agents/search.py`: `async def search_agent_node(state: PatentPilotState) -> Dict[str, Any]`
  - Inputs: `state["search_keywords"]`
  - Outputs: `{"patent_results": List[Dict[str, Any]], "research_papers": List[Dict[str, Any]]}`
  - Uses `asyncio.gather` for parallel invocation of `search_patents` and `search_papers`.

### M4: Document Processing Node
- `agents/document_processing.py`: `def document_processing_agent_node(state: PatentPilotState) -> Dict[str, Any]`
  - Inputs: `state["patent_results"]`, `state["research_papers"]`
  - Outputs: `{"raw_documents": List[Dict[str, Any]]}`
  - Format per doc: `{"source_id": str, "source_type": str, "text": str, "extraction_method": str}`
  - PyMuPDF (`fitz`) for PDF text layer -> fallback to PaddleOCR/RapidOCR (`ingestion/ocr_fallback.py`) -> fallback to abstract text. Load OCR engine once at module level.

### M5: LangGraph Wiring
- `graph.py`: Update `planner`, `search`, `document_processing` nodes to execute actual agent functions.
- Verify `graph.invoke({"user_query": "artificial intelligence patent intelligence"})` populates `search_keywords`, `patent_results`, `research_papers`, and `raw_documents`.

## Code Layout
- `agents/planner.py`
- `agents/search.py`
- `agents/document_processing.py`
- `ingestion/patentsview.py`
- `ingestion/semantic_scholar.py`
- `ingestion/ocr_fallback.py`
- `graph.py`
- `state.py`
- `tests/` or inline test modules for verification.
