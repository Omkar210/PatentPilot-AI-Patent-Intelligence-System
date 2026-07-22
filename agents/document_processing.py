"""
agents/document_processing.py — Stage 4: Document Processing Agent Node

Processes patent records and research papers from PatentPilotState.
Extracts text using a 4-tier fallback strategy:
1. PyMuPDF (fitz) PDF text layer (if >= 50 chars -> "pymupdf")
2. PaddleOCR / RapidOCR fallback for scanned PDFs (if >= 20 chars -> "rapidocr"/"paddleocr")
3. Abstract text fallback (-> "abstract_fallback")
4. Empty / title placeholder text fallback (-> "empty")

Output schema per document in state['raw_documents']:
{"source_id": str, "source_type": "patent"|"paper", "text": str, "extraction_method": str}
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import fitz  # PyMuPDF

from state import PatentPilotState
from ingestion.ocr_fallback import extract_text_ocr, get_ocr_engine_type
from ingestion.pdf_downloader import download_patent_pdf

logger = logging.getLogger(__name__)


def extract_text_from_pdf_file(pdf_path: Path) -> Tuple[str, str]:
    """
    Attempts text extraction from a local PDF file via PyMuPDF (Tier 1),
    falling back to OCR (Tier 2) if text layer is empty/scanned.

    Returns:
        tuple (extracted_text, extraction_method)
    """
    if not pdf_path or not pdf_path.exists() or not pdf_path.is_file():
        return "", ""

    try:
        # Tier 1: PyMuPDF Text Layer Extraction
        doc = fitz.open(pdf_path)
        page_texts: List[str] = []
        for page in doc:
            t = page.get_text("text")
            if t and t.strip():
                page_texts.append(t.strip())
        doc.close()

        full_text = "\n\n".join(page_texts).strip()
        if len(full_text) >= 50:
            return full_text, "pymupdf"

        # Tier 2: OCR Fallback if text layer is empty or minimal (< 50 chars)
        logger.info(
            f"PyMuPDF extracted minimal text ({len(full_text)} chars) for {pdf_path}. Triggering OCR fallback..."
        )
        ocr_text = extract_text_ocr(pdf_path)
        if len(ocr_text.strip()) >= 20:
            engine_type = get_ocr_engine_type() or "ocr_fallback"
            return ocr_text.strip(), engine_type
    except Exception as e:
        logger.warning(f"Failed PDF extraction for {pdf_path}: {e}")

    return "", ""


def process_single_document(
    doc_item: Dict[str, Any], source_type: str, default_idx: int
) -> Dict[str, Any]:
    """
    Processes a single patent or paper record using the 4-tier extraction hierarchy.
    """
    if source_type == "patent":
        source_id = str(
            doc_item.get("patent_id") or doc_item.get("id") or f"PATENT_{default_idx}"
        )
    else:
        source_id = str(
            doc_item.get("paper_id") or doc_item.get("id") or f"PAPER_{default_idx}"
        )

    pdf_path: Optional[Path] = None

    # Check if doc_item provides a local pdf_path directly
    if doc_item.get("pdf_path"):
        p = Path(doc_item["pdf_path"])
        if p.exists() and p.is_file():
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
        if title and isinstance(title, str) and len(title.strip()) > 0:
            text = f"Title: {title.strip()}"
        else:
            text = "[No text content available]"
        extraction_method = "empty"

    return {
        "source_id": source_id,
        "source_type": source_type,
        "text": text,
        "extraction_method": extraction_method,
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
                doc_record = process_single_document(
                    patent, source_type="patent", default_idx=idx + 1
                )
                raw_documents.append(doc_record)

    # Process research paper records
    if isinstance(research_papers, list):
        for idx, paper in enumerate(research_papers):
            if isinstance(paper, dict):
                doc_record = process_single_document(
                    paper, source_type="paper", default_idx=idx + 1
                )
                raw_documents.append(doc_record)

    return {"raw_documents": raw_documents}
