# Forensic Audit Report — Milestone 4: Document Processing Node & OCR Fallback (Requirement R4)

**Work Product**: `ingestion/ocr_fallback.py`, `agents/document_processing.py`, `graph.py`, `tests/test_document_processing.py`  
**Profile**: General Project (Forensic Integrity Audit)  
**Verdict**: `VERDICT: CLEAN`

---

## 1. Observation

### Codebase Inspection & Line-by-Line Findings

#### File 1: `ingestion/ocr_fallback.py` (156 lines)
- **Singleton OCR Initialization (Lines 19–52)**:
  - `get_ocr_engine()` dynamically attempts to initialize `PaddleOCR` (lines 30–36) with `use_angle_cls=True`, `lang="en"`.
  - If `PaddleOCR` raises an exception, it falls back to `RapidOCR` via `rapidocr_onnxruntime` (lines 40–46).
  - If both fail, returns `False` and logs warning.
- **Image Byte Processing (Lines 60–93)**:
  - `extract_text_from_image_bytes(img_bytes)` executes `engine(img_bytes)` for `rapidocr` or `engine.ocr(img_bytes, cls=True)` for `paddleocr`.
  - Text lines are extracted from tuple structure and joined using `\n`.
- **PDF & Byte Extraction (Lines 96–143)**:
  - `extract_text_ocr(pdf_path_or_image_bytes)` handles file paths (`str`/`Path`), raw `%PDF` bytes via `fitz.open()`, or raw image bytes.
  - Iterates pages in PyMuPDF document, converts each page to image bytes (`page.get_pixmap(dpi=200).tobytes("png")`), applies OCR via `extract_text_from_image_bytes`, and joins page outputs with `\n\n`.
- **No Hardcoded Outputs**: Code contains no pre-populated strings, fake OCR dictionaries, or shortcut returns in production code paths.

#### File 2: `agents/document_processing.py` (156 lines)
- **4-Tier Fallback Hierarchy**:
  - **Tier 1 (Lines 39–50)**: PyMuPDF (`fitz`) text layer extraction. If extracted text length $\ge 50$ characters, returns `(full_text, "pymupdf")`.
  - **Tier 2 (Lines 52–59)**: OCR fallback triggered when PyMuPDF text length $< 50$ characters. Calls `extract_text_ocr(pdf_path)`. If extracted text length $\ge 20$ characters, returns `(ocr_text, engine_type)`.
  - **Tier 3 (Lines 102–106)**: Abstract text fallback. Triggered when PDF text is empty or unavailable. Returns `(abstract.strip(), "abstract_fallback")`.
  - **Tier 4 (Lines 108–115)**: Title or empty text fallback. Returns `("Title: ...", "empty")` or `("[No text content available]", "empty")`.
- **Node Function (Lines 125–155)**:
  - `document_processing_agent_node(state: PatentPilotState) -> Dict[str, Any]` processes both `state.get("patent_results", [])` and `state.get("research_papers", [])`.
  - Returns state update dictionary `{"raw_documents": List[Dict[str, Any]]}` adhering strictly to `PatentPilotState` schema.

#### File 3: `graph.py` (120 lines)
- Imports `document_processing_agent_node` from `agents.document_processing` (line 26).
- Registers node `builder.add_node("document_processing", document_processing_agent_node)` (line 88).
- Wires sequence: `START -> user_query -> planner -> search -> document_processing -> entity_extraction -> ... -> END` (lines 98–109).

#### File 4: `tests/test_document_processing.py` (189 lines)
- 6 unit tests covering all 4 extraction tiers, pipeline node execution, and OCR error resilience:
  1. `test_document_processing_pymupdf_extraction`: Tests PyMuPDF text extraction from a generated PDF.
  2. `test_document_processing_ocr_fallback`: Tests OCR fallback monkeypatching on scanned PDF.
  3. `test_document_processing_abstract_fallback`: Tests abstract text fallback when no PDF exists.
  4. `test_document_processing_empty_fallback`: Tests Title and empty text fallback.
  5. `test_document_processing_agent_node_full_pipeline`: Tests full agent node function with mixed input state.
  6. `test_ocr_fallback_resilience`: Tests input validation and graceful failure on invalid files/bytes.

---

### Empirical Verification Outputs

1. **Targeted PyTest Execution**:
   ```
   venv\Scripts\pytest tests/test_document_processing.py -v
   ```
   *Result*: `6 passed in 0.81s`

2. **Full Workspace PyTest Execution**:
   ```
   venv\Scripts\pytest -v
   ```
   *Result*: `30 passed, 6 warnings in 9.61s`

3. **Runtime Tracing & OCR Verification**:
   - Created image-only PDF (no text layer) with PyMuPDF rendering: `PyMuPDF raw text layer count: 0`.
   - Executed `extract_text_from_pdf_file` on image PDF:
     - Output: `Extracted text: 'HIGH PERFORMANCE TENSOR ACCELERATION IN EDGE COMPUTING ARC'`
     - Extraction method: `'rapidocr'`
   - Verified active OCR engine: `RapidOCR` (`rapidocr_onnxruntime`).

---

## 2. Logic Chain

1. **Hardcoding & Cheating Analysis**:
   - Inspected `ingestion/ocr_fallback.py` and `agents/document_processing.py` line-by-line for fixed return strings, facade methods, or pre-calculated outputs.
   - Found zero instances of hardcoded outputs, fake OCR dictionaries, or bypassed logic in production code. All text extraction functions execute genuine algorithms using PyMuPDF and RapidOCR/PaddleOCR.

2. **Behavioral Functionality Analysis**:
   - Verified that `agents/document_processing.py` uses `fitz.open()` for Tier 1 PDF parsing.
   - Verified that when PyMuPDF extracts $< 50$ characters, `extract_text_ocr` is invoked.
   - Empirically verified with an image-only PDF that RapidOCR extracts text from rendered PDF images when no text layer is present.
   - Verified that Tier 3 (`abstract_fallback`) and Tier 4 (`empty`) execute correctly when PDF text is empty or missing.

3. **Test Suite Verification**:
   - Both `tests/test_document_processing.py` (6 tests) and the complete test suite (`pytest`, 30 tests across all modules) pass cleanly without failure.

4. **Integration Verification**:
   - Verified `graph.py` wires `document_processing` node between `search` and `entity_extraction` in the 11-stage LangGraph workflow.

---

## 3. Caveats

- **Network Dependency for Live PDF Downloads**: In production environments, `ingestion/pdf_downloader.py` relies on external Google Patents URLs. In unit tests, PDF downloaders are monkeypatched to ensure reliable offline execution. Real PDF parsing was verified locally using generated PDF files.
- **OCR Engine Dependency**: `RapidOCR` (`rapidocr_onnxruntime`) was used during runtime evaluation because `paddleocr` requires C++ Cuda/CPU dependencies on Windows. The module correctly fell back to `RapidOCR` as designed.

---

## 4. Conclusion

The Milestone 4 implementation (`ingestion/ocr_fallback.py`, `agents/document_processing.py`, `graph.py`, `tests/test_document_processing.py`) fully satisfies all functional and architectural requirements for Requirement R4. No hardcoded results, fake implementations, or integrity violations were detected.

**VERDICT: CLEAN**

---

## 5. Verification Method

To independently re-verify this forensic audit report:

1. **Run Stage 4 Unit Tests**:
   ```bash
   venv\Scripts\pytest tests/test_document_processing.py -v
   ```
   *Expected outcome*: 6 passing tests.

2. **Run Full Project Test Suite**:
   ```bash
   venv\Scripts\pytest -v
   ```
   *Expected outcome*: 30 passing tests.

3. **Empirical OCR Fallback Verification**:
   Run the following Python command in terminal:
   ```bash
   venv\Scripts\python -c "
   import fitz
   from pathlib import Path
   from agents.document_processing import extract_text_from_pdf_file

   doc = fitz.open()
   p = doc.new_page(width=600, height=200)
   p.insert_text((20, 50), 'TENSOR ACCELERATION IN EDGE COMPUTING', fontsize=16)
   pix = p.get_pixmap(dpi=200)
   img_bytes = pix.tobytes('png')
   doc.close()

   doc_img = fitz.open()
   page_img = doc_img.new_page(width=600, height=200)
   page_img.insert_image(fitz.Rect(0, 0, 600, 200), stream=img_bytes)
   img_pdf_path = Path('uploads/pdfs/audit_test.pdf')
   doc_img.save(img_pdf_path)
   doc_img.close()

   text, method = extract_text_from_pdf_file(img_pdf_path)
   print('Method:', method, '| Text:', repr(text))
   img_pdf_path.unlink(missing_ok=True)
   "
   ```
   *Expected outcome*: `Method: rapidocr` (or `paddleocr`), with OCR-recognized text.
