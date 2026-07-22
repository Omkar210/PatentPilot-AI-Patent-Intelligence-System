## 2026-07-22T12:23:07Z
You are worker_m4 for Milestone 4 (Document Processing Node & OCR Fallback, Requirement R4).
Working directory: d:\CDAC\Major Project\Antigravity Patent\.agents\worker_m4

Objective:
Implement Milestone 4 per the strategy detailed in `d:\CDAC\Major Project\Antigravity Patent\.agents\explorer_m4_1\handoff.md`:
1. Implement `ingestion/ocr_fallback.py`:
   - Singleton OCR loader (`get_ocr_engine`) trying `PaddleOCR` then `RapidOCR` fallback.
   - `extract_text_ocr(pdf_path_or_image_bytes)` handling PDF paths, `Path` objects, and raw bytes (rendering PDF pages to image pixmaps via PyMuPDF/`fitz` and extracting text).
   - Graceful error handling returning `""` if OCR fails or is unavailable.
2. Implement `agents/document_processing.py`:
   - `document_processing_agent_node(state: PatentPilotState) -> Dict[str, Any]`
   - 4-tier text extraction hierarchy:
     * Tier 1: PyMuPDF (`fitz`) text layer (if >= 50 chars -> method: `"pymupdf"`)
     * Tier 2: OCR fallback via `extract_text_ocr` (if >= 20 chars -> method: `"rapidocr"`/`"paddleocr"`)
     * Tier 3: Abstract text fallback (`doc.get("abstract")` -> method: `"abstract_fallback"`)
     * Tier 4: Title/empty fallback -> method: `"empty"`
   - Output schema in state: `{"raw_documents": List[Dict[str, Any]]}` with keys: `source_id`, `source_type` (`"patent"`|`"paper"`), `text`, `extraction_method`.
3. Update `graph.py`:
   - Import `document_processing_agent_node` from `agents.document_processing` and replace stub node function.
4. Implement comprehensive unit test suite in `tests/test_document_processing.py`:
   - Test PyMuPDF extraction tier.
   - Test OCR fallback tier with monkeypatching/mocking.
   - Test Abstract fallback tier.
   - Test Empty fallback tier.
   - Test `document_processing_agent_node` with state containing both patents and papers.
   - Test `ocr_fallback` module resilience on invalid/empty inputs.

Run tests:
`venv\Scripts\pytest tests/test_document_processing.py`
`venv\Scripts\pytest`

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A Forensic Auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

When finished, write your report to `d:\CDAC\Major Project\Antigravity Patent\.agents\worker_m4\handoff.md` and send a message back to orchestrator.
