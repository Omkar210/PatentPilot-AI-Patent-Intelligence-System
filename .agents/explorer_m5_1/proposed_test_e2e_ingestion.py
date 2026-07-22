"""
tests/test_e2e_ingestion.py — End-to-End Integration Tests for Ingestion Pipeline (Stages 1-4)

Verifies full workflow execution of graph.invoke() for Stages 1 through 4:
Stage 1: user_query
Stage 2: planner (LLM / NLP fallback generating 3-6 search_keywords)
Stage 3: search (PatentsView + Semantic Scholar parallel search / graceful fallbacks)
Stage 4: document_processing (4-tier text extraction hierarchy outputting raw_documents)
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path
project_root = Path(__file__).resolve().parent
while project_root.name != "Antigravity Patent" and project_root.parent != project_root:
    project_root = project_root.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import pytest
from unittest.mock import AsyncMock, patch
from typing import Dict, Any, List

from graph import graph
from state import PatentPilotState


def test_e2e_ingestion_live_or_fallback_execution():
    """
    End-to-End Integration Test: Live or Graceful Fallback Execution.
    Executes graph.invoke() with a real query and verifies state propagation across Stages 1-4.
    """
    user_query = "artificial intelligence patent intelligence"
    initial_state = {"user_query": user_query}

    # Execute full 11-stage graph (Stages 1-4 active, 5-11 stubs)
    final_state = graph.invoke(initial_state)

    # 1. Verify Stage 1 (user_query)
    assert "user_query" in final_state
    assert final_state["user_query"] == user_query

    # 2. Verify Stage 2 (planner)
    assert "search_keywords" in final_state
    keywords = final_state["search_keywords"]
    assert isinstance(keywords, list)
    assert 3 <= len(keywords) <= 6
    for kw in keywords:
        assert isinstance(kw, str)
        assert len(kw.strip()) > 0

    # 3. Verify Stage 3 (search)
    assert "patent_results" in final_state
    assert "research_papers" in final_state
    patent_results = final_state["patent_results"]
    research_papers = final_state["research_papers"]

    assert isinstance(patent_results, list)
    assert isinstance(research_papers, list)
    assert len(patent_results) > 0
    assert len(research_papers) > 0

    # 4. Verify Stage 4 (document_processing)
    assert "raw_documents" in final_state
    raw_documents = final_state["raw_documents"]
    assert isinstance(raw_documents, list)
    assert len(raw_documents) == len(patent_results) + len(research_papers)

    # Mandatory keys schema validation per document
    mandatory_keys = {"source_id", "source_type", "text", "extraction_method"}
    valid_extraction_methods = {
        "pymupdf",
        "rapidocr",
        "paddleocr",
        "ocr_fallback",
        "abstract_fallback",
        "empty",
    }

    for doc in raw_documents:
        assert isinstance(doc, dict)
        assert mandatory_keys.issubset(doc.keys()), f"Missing keys in document: {set(mandatory_keys) - set(doc.keys())}"
        assert isinstance(doc["source_id"], str)
        assert len(doc["source_id"]) > 0
        assert doc["source_type"] in ["patent", "paper"]
        assert isinstance(doc["text"], str)
        assert len(doc["text"]) > 0
        assert doc["extraction_method"] in valid_extraction_methods


def test_e2e_ingestion_mocked_execution():
    """
    End-to-End Integration Test: Deterministic Mocked Execution.
    Mocks external search APIs and PDF downloading to test pipeline wiring and data contracts.
    """
    mock_patents = [
        {
            "patent_id": "US10000000B2",
            "title": "AI Patent Analytics System",
            "abstract": "An artificial intelligence system for automated patent analysis and classification.",
            "inventors": ["Jane Doe"],
            "ipc_codes": ["G06N 20/00"],
            "pdf_url": "https://example.com/patent.pdf",
        }
    ]

    mock_papers = [
        {
            "paper_id": "S2_PAPER_999",
            "title": "Machine Learning in Patent Prior Art Search",
            "abstract": "A novel graph neural network approach for patent similarity search.",
            "url": "https://semanticscholar.org/paper/999",
            "year": 2025,
            "authors": ["John Smith"],
        }
    ]

    with patch(
        "agents.search.fetch_patents", new_callable=AsyncMock
    ) as mock_fetch_patents, patch(
        "agents.search.fetch_papers", new_callable=AsyncMock
    ) as mock_fetch_papers, patch(
        "agents.document_processing.download_patent_pdf", return_value=None
    ):
        mock_fetch_patents.return_value = mock_patents
        mock_fetch_papers.return_value = mock_papers

        user_query = "artificial intelligence patent intelligence"
        final_state = graph.invoke({"user_query": user_query})

        # Assert Stage 1
        assert final_state["user_query"] == user_query

        # Assert Stage 2
        assert 3 <= len(final_state["search_keywords"]) <= 6

        # Assert Stage 3
        assert final_state["patent_results"] == mock_patents
        assert final_state["research_papers"] == mock_papers

        # Assert Stage 4
        raw_docs = final_state["raw_documents"]
        assert len(raw_docs) == 2

        # Check patent document in raw_documents
        patent_doc = next(d for d in raw_docs if d["source_id"] == "US10000000B2")
        assert patent_doc["source_type"] == "patent"
        assert "automated patent analysis" in patent_doc["text"]
        assert patent_doc["extraction_method"] == "abstract_fallback"

        # Check paper document in raw_documents
        paper_doc = next(d for d in raw_docs if d["source_id"] == "S2_PAPER_999")
        assert paper_doc["source_type"] == "paper"
        assert "graph neural network approach" in paper_doc["text"]
        assert paper_doc["extraction_method"] == "abstract_fallback"


def test_e2e_ingestion_empty_query_fallback():
    """
    End-to-End Integration Test: Empty Query Fallback.
    Ensures empty or whitespace query is handled safely through Stages 1-4.
    """
    with patch(
        "agents.document_processing.download_patent_pdf", return_value=None
    ):
        final_state = graph.invoke({"user_query": ""})

        assert final_state["user_query"] == ""
        assert len(final_state["search_keywords"]) >= 3
        assert len(final_state["patent_results"]) > 0
        assert len(final_state["research_papers"]) > 0
        assert len(final_state["raw_documents"]) > 0
