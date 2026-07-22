import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import fitz  # PyMuPDF

from state import PatentPilotState
from agents.document_processing import (
    document_processing_agent_node,
    process_single_document,
    extract_text_from_pdf_file,
)
from ingestion.ocr_fallback import (
    extract_text_ocr,
    get_ocr_engine,
    get_ocr_engine_type,
    extract_text_from_image_bytes,
)


def test_document_processing_pymupdf_extraction(tmp_path: Path):
    """Test Tier 1: PyMuPDF text layer extraction from a valid text PDF."""
    pdf_file = tmp_path / "test_patent.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(
        (50, 50),
        "This is a detailed patent text description regarding neural network hardware optimization and matrix multiplication acceleration.",
    )
    doc.save(pdf_file)
    doc.close()

    patent_item = {
        "patent_id": "US10123456B2",
        "title": "Neural Network Optimization",
        "abstract": "Patent abstract text",
        "pdf_path": str(pdf_file),
    }

    res = process_single_document(patent_item, source_type="patent", default_idx=1)

    assert res["source_id"] == "US10123456B2"
    assert res["source_type"] == "patent"
    assert "neural network hardware optimization" in res["text"].lower()
    assert res["extraction_method"] == "pymupdf"


def test_document_processing_ocr_fallback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Test Tier 2: OCR fallback when PDF has scanned page/empty text layer."""
    pdf_file = tmp_path / "scanned_patent.pdf"
    doc = fitz.open()
    doc.new_page()  # Empty text layer page
    doc.save(pdf_file)
    doc.close()

    monkeypatch.setattr(
        "agents.document_processing.extract_text_ocr",
        lambda path: "OCR Extracted Text: Method for high performance tensor acceleration in edge computing.",
    )
    monkeypatch.setattr("agents.document_processing.get_ocr_engine_type", lambda: "rapidocr")

    patent_item = {
        "patent_id": "US9999999B1",
        "title": "Scanned Patent Title",
        "abstract": "Fallback abstract",
        "pdf_path": str(pdf_file),
    }

    res = process_single_document(patent_item, source_type="patent", default_idx=1)

    assert res["source_id"] == "US9999999B1"
    assert res["source_type"] == "patent"
    assert "tensor acceleration" in res["text"].lower()
    assert res["extraction_method"] in ["rapidocr", "paddleocr", "ocr_fallback"]


def test_document_processing_abstract_fallback(monkeypatch: pytest.MonkeyPatch):
    """Test Tier 3: Abstract fallback when PDF downloader fails / no PDF exists."""
    monkeypatch.setattr(
        "agents.document_processing.download_patent_pdf",
        lambda patent_id, pdf_url=None: None,
    )

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


def test_document_processing_empty_fallback(monkeypatch: pytest.MonkeyPatch):
    """Test Tier 4: Empty fallback when no PDF exists and abstract is missing/empty."""
    monkeypatch.setattr(
        "agents.document_processing.download_patent_pdf",
        lambda patent_id, pdf_url=None: None,
    )

    empty_item = {
        "patent_id": "US7777777B2",
        "title": "Bare Patent Without Abstract",
        "abstract": "",
    }

    res = process_single_document(empty_item, source_type="patent", default_idx=1)

    assert res["source_id"] == "US7777777B2"
    assert res["extraction_method"] == "empty"
    assert "Bare Patent Without Abstract" in res["text"]

    no_title_item = {
        "paper_id": "PAPER_NO_TITLE",
        "abstract": "",
    }
    res_no_title = process_single_document(no_title_item, source_type="paper", default_idx=2)
    assert res_no_title["source_id"] == "PAPER_NO_TITLE"
    assert res_no_title["extraction_method"] == "empty"
    assert res_no_title["text"] == "[No text content available]"


def test_document_processing_agent_node_full_pipeline(monkeypatch: pytest.MonkeyPatch):
    """Test document_processing_agent_node with state containing both patents and papers."""
    monkeypatch.setattr(
        "agents.document_processing.download_patent_pdf",
        lambda patent_id, pdf_url=None: None,
    )

    state: PatentPilotState = {
        "patent_results": [
            {"patent_id": "US101", "title": "Patent 1", "abstract": "Abstract 1"},
            {"patent_id": "US102", "title": "Patent 2", "abstract": "Abstract 2"},
        ],
        "research_papers": [
            {"paper_id": "PAPER201", "title": "Paper 1", "abstract": "Paper Abstract 1"}
        ],
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


def test_ocr_fallback_resilience():
    """Test ocr_fallback module functions gracefully with invalid inputs or missing files."""
    res_empty_path = extract_text_ocr("non_existent_file.pdf")
    assert res_empty_path == ""

    res_empty_bytes = extract_text_ocr(b"")
    assert res_empty_bytes == ""

    res_none = extract_text_ocr(None)  # type: ignore
    assert res_none == ""

    res_empty_img = extract_text_from_image_bytes(b"")
    assert res_empty_img == ""
