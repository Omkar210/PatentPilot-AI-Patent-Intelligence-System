# Original User Request

## 2026-07-22T12:04:34+05:30

Build the Data Ingestion pipeline for PatentPilot AI in working directory: d:\CDAC\Major Project\Antigravity Patent

## Requirements

### R1. API Clients for PatentsView & Semantic Scholar (`/ingestion`)
Build async HTTP clients (`httpx 0.28.1`) for searching PatentsView (USPTO patents) in `ingestion/patentsview.py` and Semantic Scholar (research papers) in `ingestion/semantic_scholar.py`. Handle rate limits and retries gracefully.

### R2. Planner Agent (`agents/planner.py`)
Implement the Planner agent node taking `state["user_query"]` and generating 3–6 focused search keywords as structured JSON output using hosted LLM API (Google Gemini 2.5 Flash / Groq fallback, temperature 0).

### R3. Search Agent Node (`agents/search.py`)
Implement the Search agent node executing PatentsView and Semantic Scholar API clients concurrently via `asyncio.gather`, writing output records into `patent_results` and `research_papers` in `PatentPilotState`.

### R4. Document Processing Node (`agents/document_processing.py`)
Implement document text extraction for patent results: use PyMuPDF (`fitz`) for PDF text layers, fall back to PaddleOCR/RapidOCR engine (`ingestion/ocr_fallback.py`) for scanned image pages, or use abstract text if no PDF path exists. Load OCR engine once at module level.

### R5. Workflow Wiring & Verification (`graph.py` & test)
Replace stub functions in `graph.py` with real agent nodes for stages 2 (planner), 3 (search), and 4 (document processing). Execute an end-to-end test query through the pipeline and verify output state.

## Acceptance Criteria
- [ ] `ingestion/patentsview.py` queries PatentsView API and returns structured patent records.
- [ ] `ingestion/semantic_scholar.py` queries Semantic Scholar API and returns structured paper records.
- [ ] `agents/planner.py` extracts 3–6 search keywords from `user_query` as valid JSON array.
- [ ] `agents/search.py` executes search clients concurrently with `asyncio.gather`.
- [ ] `agents/document_processing.py` extracts document text via PyMuPDF with OCR fallback.
- [ ] `graph.invoke({"user_query": "artificial intelligence patent intelligence"})` populates `search_keywords`, `patent_results`, `research_papers`, and `raw_documents` in `PatentPilotState`.
- [ ] All automated tests pass without errors.
