# Execution Plan — Data Ingestion Pipeline (R1–R5)

## Overview
This plan governs the implementation of Requirements R1 through R5 for the PatentPilot AI Data Ingestion pipeline.

## Milestone Schedule

### Milestone 1: API Clients for PatentsView & Semantic Scholar (R1)
- **Goal**: Implement `ingestion/patentsview.py` and `ingestion/semantic_scholar.py` using `httpx` async client with rate limits and retry logic.
- **Verification**: Dedicated test script exercising real/mocked API responses with structured dict returns.
- **Workflow**: Explorer -> Worker -> Reviewer -> Forensic Auditor -> Gate.

### Milestone 2: Planner Agent (R2)
- **Goal**: Implement `agents/planner.py` to extract 3–6 search keywords from `state["user_query"]` as a JSON array using hosted LLM API (Gemini / Groq).
- **Verification**: Test with sample queries checking array length (3–6) and type safety.
- **Workflow**: Explorer -> Worker -> Reviewer -> Forensic Auditor -> Gate.

### Milestone 3: Search Agent Node (R3)
- **Goal**: Implement `agents/search.py` executing PatentsView and Semantic Scholar clients concurrently via `asyncio.gather`, updating `PatentPilotState`.
- **Verification**: Test with search keywords, verifying concurrent execution and output structure in state.
- **Workflow**: Explorer -> Worker -> Reviewer -> Forensic Auditor -> Gate.

### Milestone 4: Document Processing Node (R4)
- **Goal**: Implement `agents/document_processing.py` extracting document text via PyMuPDF (`fitz`), fallback to PaddleOCR/RapidOCR engine (`ingestion/ocr_fallback.py`), or fallback to abstract text.
- **Verification**: Test PDF text extraction, OCR fallback path, and abstract text fallback.
- **Workflow**: Explorer -> Worker -> Reviewer -> Forensic Auditor -> Gate.

### Milestone 5: LangGraph Wiring & E2E Verification (R5)
- **Goal**: Wire real agent nodes into `graph.py` for stages 2, 3, and 4. Execute end-to-end pipeline invocation.
- **Verification**: Run `graph.invoke({"user_query": "artificial intelligence patent intelligence"})` and verify state fields (`search_keywords`, `patent_results`, `research_papers`, `raw_documents`). Run full test suite.
- **Workflow**: Explorer -> Worker -> Reviewer -> Forensic Auditor -> Gate.
