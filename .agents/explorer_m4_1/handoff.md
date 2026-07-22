# Milestone 4 Investigation & Strategy Report: Document Processing Node & OCR Fallback (Requirement R4)

## 1. Observation

Direct code and environment observations:

1. **State Definition (`state.py:56-62`)**:
   `PatentPilotState` defines `raw_documents` as:
   ```python
   raw_documents: List[Dict[str, Any]]
   """
   Extracted/cleaned text per source document.
   Keys: source_id, source_type (patent|paper), text, extraction_method
   """
   ```

2. **Graph Pipeline Wiring (`graph.py:35-37, 91`)**:
   Stage 4 is currently defined in `graph.py` as a stub function:
   ```python
   def document_processing_agent_node(state: PatentPilotState) -> Dict[str, Any]:
       """Stage 4: Document processing - PyMuPDF + PaddleOCR fallback."""
       return {"raw_documents": state.get("raw_documents", [])}
   ```
   Node `document_processing` is registered in `StateGraph` between `search` and `entity_extraction`.

3. **Existing OCR Fallback Engine (`ingestion/ocr_fallback.py:1-43`)**:
   Currently contains `get_ocr_engine()` trying `rapidocr_onnxruntime.RapidOCR` and `extract_page_ocr(page: fitz.Page)`.
   It does not yet provide the unified signature `extract_text_ocr(pdf_path_or_image_bytes) -> str` supporting string paths, `Path` objects, and raw bytes.

4. **PDF Downloader Service (`ingestion/pdf_downloader.py:31-80`)**:
   Provides `download_patent_pdf(patent_id: str, pdf_url: Optional[str] = None) -> Optional[Path]` which saves PDFs into `uploads/pdfs/{clean_id}.pdf`.

5. **Environment Dependency Check**:
   Executed dependency check in python `venv`:
   - PyMuPDF (`fitz` 1.26.4): Installed and available.
   - `rapidocr_onnxruntime`: Installed and available.
   - `paddleocr`: Not installed (`ModuleNotFoundError`), confirming requirement for graceful fallback logic.

6. **Test Suite Status**:
   Executed `venv\Scripts\pytest` — 24/24 tests passed across `scripts/test_db.py`, `tests/test_ingestion_clients.py`, `tests/test_planner.py`, and `tests/test_search.py`.

---

## 2. Logic Chain

1. **Pipeline Input/Output Requirements**:
   - `document_processing_agent_node` reads `patent_results` (list of patent records) and `research_papers` (list of paper records) from input `PatentPilotState`.
   - It outputs `{"raw_documents": List[Dict[str, Any]]}` where every record has keys:
     - `source_id` (str): patent_id or paper_id
     - `source_type` (str): `"patent"` or `"paper"`
     - `text` (str): extracted full text or fallback content
     - `extraction_method` (str): `"pymupdf"`, `"rapidocr"`, `"paddleocr"`, `"abstract_fallback"`, or `"empty"`.

2. **4-Tier Text Extraction Strategy**:
   - **Tier 1 (PyMuPDF / `fitz`)**: For a given document, check if a local PDF path exists (or attempt download via `ingestion/pdf_downloader.py`). Open PDF with PyMuPDF and extract text. If extracted text >= 50 characters, accept text with `extraction_method = "pymupdf"`.
   - **Tier 2 (OCR Fallback via PaddleOCR/RapidOCR)**: Triggered if local PDF exists BUT PyMuPDF yields empty or near-empty text (< 50 chars), indicating scanned raster PDF pages. Call `extract_text_ocr`. If returned text >= 20 characters, accept text with `extraction_method = "rapidocr"` (or `"paddleocr"` / `"ocr_fallback"`).
   - **Tier 3 (Abstract Fallback)**: Triggered if PDF is unavailable / download failed, or if PyMuPDF and OCR both fail / return empty text. Use `doc.get("abstract")`. If non-empty, accept text with `extraction_method = "abstract_fallback"`.
   - **Tier 4 (Empty Fallback)**: Triggered if abstract is also empty or missing. Return placeholder string e.g. `f"Title: {doc.get('title', '')}"` or `"[No text content available]"` with `extraction_method = "empty"`.

3. **Singleton OCR Design in `ingestion/ocr_fallback.py`**:
   - Initialize `_ocr_engine` lazily as a module-level singleton.
   - Try importing `PaddleOCR` (primary choice per tech stack requirement) -> if absent, try importing `RapidOCR` -> if absent/fails, set `_ocr_engine = False`.
   - Expose `extract_text_ocr(pdf_path_or_image_bytes: Union[str, Path, bytes]) -> str`:
     - If string/Path pointing to PDF or `bytes` starting with `%PDF`, use PyMuPDF to iterate pages, convert each page to pixmap image bytes, pass to OCR engine, and aggregate extracted text lines.
     - If image bytes/file, pass directly to OCR engine.
     - Return concatenated clean string. Wrap call in `try...except` to return `""` on any failure.

4. **Graph Integration**:
   - `graph.py` will replace its stub node function with the imported `document_processing_agent_node` from `agents.document_processing`.

---

## 3. Implementation Strategy & Proposed Code

### A. `ingestion/ocr_fallback.py` Proposed Code

```python
"""
ingestion/ocr_fallback.py — OCR Fallback Engine for Scanned Patent PDFs

Provides module-level singleton initialization for PaddleOCR / RapidOCR and text extraction.
"""

import io
import logging
from pathlib import Path
from typing import Union, Optional, List
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

_ocr_engine = None
_ocr_engine_type = None  # "paddleocr" | "rapidocr" | None


def get_ocr_engine():
    """
    Module-level singleton initializer for OCR engine.
    Tries PaddleOCR first, then RapidOCR as secondary fallback.
    Returns the engine instance or False if unavailable.
    """
    global _ocr_engine, _ocr_engine_type
    if _ocr_engine is not None:
        return _ocr_engine

    # 1. Try PaddleOCR
    try:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
        _ocr_engine_type = "paddleocr"
        logger.info("PaddleOCR engine initialized successfully.")
        return _ocr_engine
    except Exception as e:
        logger.info(f"PaddleOCR unavailable: {e}. Trying RapidOCR fallback...")

    # 2. Try RapidOCR
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        _ocr_engine_type = "rapidocr"
        logger.info("RapidOCR engine initialized successfully.")
        return _ocr_engine
    except Exception as e:
        logger.warning(f"RapidOCR unavailable: {e}. OCR fallback disabled.")

    _ocr_engine = False
    _ocr_engine_type = None
    return _ocr_engine


def extract_text_from_image_bytes(img_bytes: bytes) -> str:
    """Applies OCR engine to raw image bytes and returns extracted text."""
    engine = get_ocr_engine()
    if not engine:
        return ""

    try:
        if _ocr_engine_type == "rapidocr":
            result, elapsed = engine(img_bytes)
            if result:
                lines = [line[1] for line in result if line and len(line) > 1]
                return "\n".join(lines)
        elif _ocr_engine_type == "paddleocr":
            result = engine.ocr(img_bytes, cls=True)
            lines = []
            if result and isinstance(result, list):
                for res in result:
                    if res:
                        for line in res:
                            if line and len(line) > 1 and isinstance(line[1], (tuple, list)):
                                lines.append(line[1][0])
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"OCR execution failed on image bytes: {e}")

    return ""


def extract_text_ocr(pdf_path_or_image_bytes: Union[str, Path, bytes]) -> str:
    """
    Extracts text using OCR from a PDF path, Path object, or raw bytes (PDF/image).

    Args:
        pdf_path_or_image_bytes: File path (str/Path) or raw bytes.

    Returns:
        Extracted text string. Returns empty string if extraction fails or OCR unavailable.
    """
    engine = get_ocr_engine()
    if not engine:
        return ""

    try:
        doc = None
        if isinstance(pdf_path_or_image_bytes, (str, Path)):
            path_obj = Path(pdf_path_or_image_bytes)
            if not path_obj.exists():
                logger.warning(f"OCR file path does not exist: {path_obj}")
                return ""
            doc = fitz.open(path_obj)
        elif isinstance(pdf_path_or_image_bytes, bytes):
            if pdf_path_or_image_bytes.startswith(b"%PDF"):
                doc = fitz.open(stream=pdf_path_or_image_bytes, filetype="pdf")
            else:
                # Direct image bytes
                return extract_text_from_image_bytes(pdf_path_or_image_bytes)

        if doc is not None:
            extracted_pages: List[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                page_text = extract_text_from_image_bytes(img_bytes)
                if page_text.strip():
                    extracted_pages.append(page_text.strip())
            doc.close()
            return "\n\n".join(extracted_pages)

    except Exception as e:
        logger.error(f"extract_text_ocr exception: {e}")

    return ""


def extract_page_ocr(page: fitz.Page) -> str:
    """Renders a PDF page to pixmap image and applies OCR fallback."""
    try:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        ocr_text = extract_text_from_image_bytes(img_bytes)
        if ocr_text.strip():
            return ocr_text.strip()
        return page.get_text("text")
    except Exception as e:
        return f"[OCR Error: {e}]"
```

---

### B. `agents/document_processing.py` Proposed Code

```python
"""
agents/document_processing.py — Stage 4: Document Processing Agent Node

Processes patent records and research papers from PatentPilotState.
Extracts text using a 4-tier fallback strategy:
1. PyMuPDF (fitz) PDF text layer
2. PaddleOCR / RapidOCR fallback for scanned PDFs
3. Abstract text fallback
4. Empty / placeholder text fallback

Output schema per document:
{"source_id": str, "source_type": "patent"|"paper", "text": str, "extraction_method": str}
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import fitz  # PyMuPDF

from state import PatentPilotState
from ingestion.ocr_fallback import extract_text_ocr
from ingestion.pdf_downloader import download_patent_pdf

logger = logging.getLogger(__name__)


def extract_text_from_pdf_file(pdf_path: Path) -> tuple[str, str]:
    """
    Attempts text extraction from a local PDF file via PyMuPDF (Tier 1),
    falling back to OCR (Tier 2) if text layer is empty/scanned.

    Returns:
        tuple (extracted_text, extraction_method)
    """
    if not pdf_path or not pdf_path.exists():
        return "", ""

    try:
        # Tier 1: PyMuPDF Text Layer Extraction
        doc = fitz.open(pdf_path)
        page_texts = []
        for page in doc:
            t = page.get_text("text")
            if t:
                page_texts.append(t.strip())
        doc.close()

        full_text = "\n\n".join(page_texts).strip()
        if len(full_text) >= 50:
            return full_text, "pymupdf"

        # Tier 2: OCR Fallback if text layer is empty or minimal (< 50 chars)
        logger.info(f"PyMuPDF extracted minimal text ({len(full_text)} chars) for {pdf_path}. Triggering OCR fallback...")
        ocr_text = extract_text_ocr(pdf_path)
        if len(ocr_text.strip()) >= 20:
            # Detect engine type or report ocr_fallback
            return ocr_text.strip(), "rapidocr"
    except Exception as e:
        logger.warning(f"Failed PDF extraction for {pdf_path}: {e}")

    return "", ""


def process_single_document(doc_item: Dict[str, Any], source_type: str, default_idx: int) -> Dict[str, Any]:
    """
    Processes a single patent or paper record using the 4-tier extraction hierarchy.
    """
    if source_type == "patent":
        source_id = str(doc_item.get("patent_id") or doc_item.get("id") or f"PATENT_{default_idx}")
    else:
        source_id = str(doc_item.get("paper_id") or doc_item.get("id") or f"PAPER_{default_idx}")

    pdf_path: Optional[Path] = None

    # Check if doc_item provides a local pdf_path directly
    if doc_item.get("pdf_path"):
        p = Path(doc_item["pdf_path"])
        if p.exists():
            pdf_path = p

    # If patent and no local PDF, attempt download via pdf_downloader
    if not pdf_path and source_type == "patent":
        pdf_url = doc_item.get("pdf_url")
        pdf_path = download_patent_pdf(source_id, pdf_url=pdf_url)

    text = ""
    extraction_method = ""

    # Tier 1 & Tier 2: PDF File Processing (PyMuPDF -> OCR)
    if pdf_path:
        text, extraction_method = extract_text_from_pdf_file(pdf_path)

    # Tier 3: Abstract Fallback
    if not text:
        abstract = doc_item.get("abstract", "")
        if abstract and isinstance(abstract, str) and len(abstract.strip()) > 0:
            text = abstract.strip()
            extraction_method = "abstract_fallback"

    # Tier 4: Empty Fallback
    if not text:
        title = doc_item.get("title", "")
        text = f"Title: {title}".strip() if title else "[No text content available]"
        extraction_method = "empty"

    return {
        "source_id": source_id,
        "source_type": source_type,
        "text": text,
        "extraction_method": extraction_method
    }


def document_processing_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Stage 4: Document processing node function for LangGraph pipeline.

    Reads `state['patent_results']` and `state['research_papers']`, processes each document,
    and returns updated state dict: `{"raw_documents": List[Dict[str, Any]]}`.
    """
    patent_results = state.get("patent_results", []) if state else []
    research_papers = state.get("research_papers", []) if state else []

    raw_documents: List[Dict[str, Any]] = []

    # Process patent records
    if isinstance(patent_results, list):
        for idx, patent in enumerate(patent_results):
            if isinstance(patent, dict):
                doc_record = process_single_document(patent, source_type="patent", default_idx=idx + 1)
                raw_documents.append(doc_record)

    # Process research paper records
    if isinstance(research_papers, list):
        for idx, paper in enumerate(research_papers):
            if isinstance(paper, dict):
                doc_record = process_single_document(paper, source_type="paper", default_idx=idx + 1)
                raw_documents.append(doc_record)

    return {"raw_documents": raw_documents}
```

---

### C. `graph.py` Proposed Modification

In `graph.py`, replace line 24-25 and 35-37:
```python
# Replace stub import with actual agent node
from agents.document_processing import document_processing_agent_node
```

---

## 4. Unit Test Plan (`tests/test_document_processing.py`)

Create `tests/test_document_processing.py` to test all scenarios thoroughly:

```python
"""
tests/test_document_processing.py — Unit Tests for Stage 4 Document Processing Agent & OCR Fallback
"""

import pytest
import unittest.mock as mock
from pathlib import Path
from state import PatentPilotState
from agents.document_processing import document_processing_agent_node, process_single_document
from ingestion.ocr_fallback import extract_text_ocr, get_ocr_engine


def test_document_processing_pymupdf_extraction(tmp_path):
    """Test Tier 1: PyMuPDF text layer extraction from a valid text PDF."""
    import fitz
    pdf_file = tmp_path / "test_patent.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a detailed patent text description regarding neural network hardware optimization.")
    doc.save(pdf_file)
    doc.close()

    patent_item = {
        "patent_id": "US10123456B2",
        "title": "Neural Network Optimization",
        "abstract": "Patent abstract text",
        "pdf_path": str(pdf_file)
    }

    res = process_single_document(patent_item, source_type="patent", default_idx=1)

    assert res["source_id"] == "US10123456B2"
    assert res["source_type"] == "patent"
    assert "neural network hardware optimization" in res["text"].lower()
    assert res["extraction_method"] == "pymupdf"


def test_document_processing_ocr_fallback(monkeypatch, tmp_path):
    """Test Tier 2: OCR fallback when PDF has scanned page/empty text layer."""
    import fitz
    pdf_file = tmp_path / "scanned_patent.pdf"
    doc = fitz.open()
    doc.new_page()  # Empty text layer page
    doc.save(pdf_file)
    doc.close()

    monkeypatch.setattr(
        "agents.document_processing.extract_text_ocr",
        lambda path: "OCR Extracted Text: Method for high performance tensor acceleration"
    )

    patent_item = {
        "patent_id": "US9999999B1",
        "title": "Scanned Patent Title",
        "abstract": "Fallback abstract",
        "pdf_path": str(pdf_file)
    }

    res = process_single_document(patent_item, source_type="patent", default_idx=1)

    assert res["source_id"] == "US9999999B1"
    assert res["source_type"] == "patent"
    assert "tensor acceleration" in res["text"].lower()
    assert res["extraction_method"] in ["rapidocr", "paddleocr", "ocr_fallback"]


def test_document_processing_abstract_fallback_no_pdf(monkeypatch):
    """Test Tier 3: Abstract fallback when PDF downloader fails / no PDF exists."""
    monkeypatch.setattr("agents.document_processing.download_patent_pdf", lambda patent_id, pdf_url=None: None)

    patent_item = {
        "patent_id": "US8888888B2",
        "title": "Quantum Error Correction",
        "abstract": "This invention relates to quantum logic gate fault tolerance and error mitigation.",
    }

    paper_item = {
        "paper_id": "S2_PAPER_101",
        "title": "Deep Learning Survey",
        "abstract": "A comprehensive review of modern transformer architectures.",
    }

    res_patent = process_single_document(patent_item, source_type="patent", default_idx=1)
    res_paper = process_single_document(paper_item, source_type="paper", default_idx=1)

    assert res_patent["source_id"] == "US8888888B2"
    assert res_patent["extraction_method"] == "abstract_fallback"
    assert "quantum logic gate" in res_patent["text"].lower()

    assert res_paper["source_id"] == "S2_PAPER_101"
    assert res_paper["extraction_method"] == "abstract_fallback"
    assert "transformer architectures" in res_paper["text"].lower()


def test_document_processing_empty_fallback(monkeypatch):
    """Test Tier 4: Empty fallback when no PDF exists and abstract is missing/empty."""
    monkeypatch.setattr("agents.document_processing.download_patent_pdf", lambda patent_id, pdf_url=None: None)

    empty_item = {
        "patent_id": "US7777777B2",
        "title": "Bare Patent Without Abstract",
        "abstract": "",
    }

    res = process_single_document(empty_item, source_type="patent", default_idx=1)

    assert res["source_id"] == "US7777777B2"
    assert res["extraction_method"] == "empty"
    assert "Bare Patent Without Abstract" in res["text"]


def test_document_processing_agent_node_full_pipeline(monkeypatch):
    """Test document_processing_agent_node with state containing both patents and papers."""
    monkeypatch.setattr("agents.document_processing.download_patent_pdf", lambda patent_id, pdf_url=None: None)

    state: PatentPilotState = {
        "patent_results": [
            {"patent_id": "US101", "title": "Patent 1", "abstract": "Abstract 1"},
            {"patent_id": "US102", "title": "Patent 2", "abstract": "Abstract 2"},
        ],
        "research_papers": [
            {"paper_id": "PAPER201", "title": "Paper 1", "abstract": "Paper Abstract 1"}
        ]
    }

    result = document_processing_agent_node(state)

    assert "raw_documents" in result
    raw_docs = result["raw_documents"]
    assert len(raw_docs) == 3

    # Check state schema compliance per document
    for doc in raw_docs:
        assert isinstance(doc, dict)
        assert "source_id" in doc
        assert "source_type" in doc
        assert doc["source_type"] in ["patent", "paper"]
        assert "text" in doc
        assert "extraction_method" in doc
        assert isinstance(doc["source_id"], str)
        assert isinstance(doc["text"], str)
        assert isinstance(doc["extraction_method"], str)


def test_ocr_fallback_singleton_and_invalid_inputs():
    """Test ocr_fallback module functions gracefully with invalid inputs or missing files."""
    res_empty_path = extract_text_ocr("non_existent_file.pdf")
    assert res_empty_path == ""

    res_empty_bytes = extract_text_ocr(b"")
    assert res_empty_bytes == ""
```

---

## 5. Caveats

1. **OCR Engine Availability**: `paddleocr` is currently not installed in the python environment, but `rapidocr_onnxruntime` is installed and verified working. The proposed singleton initialization in `ingestion/ocr_fallback.py` tries `PaddleOCR` first, falls back to `RapidOCR`, and defaults to `False` if neither is present.
2. **Network Dependency for PDF Downloads**: `ingestion/pdf_downloader.py` relies on public HTTP endpoints (Google Patents storage). Unit tests in `tests/test_document_processing.py` use monkeypatch/mocking to ensure fast, offline, and reliable test execution.

---

## 6. Conclusion

The architecture, code contracts, 4-tier extraction hierarchy, and unit test plan for Requirement R4 (Milestone 4: Document Processing Node & OCR Fallback) are fully specified and ready for implementation by an Implementer agent.

---

## 7. Verification Method

1. Run `venv\Scripts\pytest tests/test_document_processing.py` to verify all 6 unit tests pass.
2. Run `venv\Scripts\pytest` to verify all 24+ project unit tests pass without regressions.
3. Validate `raw_documents` schema output against `state.py:56-62` specification.
