"""
tests/test_ingestion_clients.py — Unit Tests for PatentsView & Semantic Scholar API Clients
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from ingestion.patentsview import fetch_patents, _parse_patent_record, _get_fallback_patents
from ingestion.semantic_scholar import fetch_papers, _parse_paper_record, _get_fallback_papers


# ── 1. PatentsView Client Tests ────────────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_patents_success():
    """Test fetch_patents successfully parses raw PatentsView API response."""
    mock_response_data = {
        "patents": [
            {
                "patent_id": "US10123456B2",
                "patent_title": "Neural Network Classifier for Medical Imaging",
                "patent_abstract": "A deep learning method for classifying radiological images.",
                "inventors": [
                    {"inventor_first_name": "Alice", "inventor_last_name": "Smith"},
                    {"inventor_first_name": "Bob", "inventor_last_name": "Jones"}
                ],
                "ipc_codes": [
                    {"cpc_subclass_id": "G06N 3/08"},
                    {"cpc_subclass_id": "G06T 7/00"}
                ]
            }
        ]
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        results = await fetch_patents(keywords=["neural network", "imaging"], limit=5)

        assert len(results) == 1
        record = results[0]

        # Verify exact required keys
        expected_keys = {"patent_id", "title", "abstract", "inventors", "ipc_codes", "pdf_url"}
        assert set(record.keys()) == expected_keys

        assert record["patent_id"] == "US10123456B2"
        assert record["title"] == "Neural Network Classifier for Medical Imaging"
        assert "deep learning" in record["abstract"]
        assert record["inventors"] == ["Alice Smith", "Bob Jones"]
        assert record["ipc_codes"] == ["G06N 3/08", "G06T 7/00"]
        assert record["pdf_url"] == "https://patentimages.storage.googleapis.com/pages/US10123456B2.pdf"


@pytest.mark.asyncio
async def test_fetch_patents_retry_429():
    """Test fetch_patents retries on HTTP 429 rate limit and succeeds on subsequent attempt."""
    mock_429_resp = MagicMock(spec=httpx.Response)
    mock_429_resp.status_code = 429
    mock_429_resp.headers = {"Retry-After": "0.01"}

    mock_200_resp = MagicMock(spec=httpx.Response)
    mock_200_resp.status_code = 200
    mock_200_resp.json.return_value = {
        "patents": [
            {
                "patent_id": "US11111111B2",
                "patent_title": "Quantum Computing Optimization Method",
                "patent_abstract": "Method using quantum annealer.",
                "inventors": [{"inventor_first_name": "Charlie", "inventor_last_name": "Brown"}],
                "ipc_codes": ["G06N 10/00"]
            }
        ]
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [mock_429_resp, mock_200_resp]

        results = await fetch_patents(keywords="quantum", max_retries=2)

        assert mock_post.call_count == 2
        assert len(results) == 1
        assert results[0]["patent_id"] == "US11111111B2"


@pytest.mark.asyncio
async def test_fetch_patents_fallback_on_error():
    """Test fetch_patents gracefully returns fallback records when request repeatedly fails."""
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = httpx.ConnectTimeout("Connection timed out")

        results = await fetch_patents(keywords="autonomous vehicles", max_retries=1)

        assert len(results) > 0
        record = results[0]
        expected_keys = {"patent_id", "title", "abstract", "inventors", "ipc_codes", "pdf_url"}
        assert set(record.keys()) == expected_keys
        assert "Autonomous Vehicles" in record["title"] or "Autonomous" in record["abstract"]


@pytest.mark.asyncio
async def test_fetch_patents_empty_response_fallback():
    """Test fetch_patents returns fallback records when API returns empty patent array."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"patents": []}

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        results = await fetch_patents(keywords="nonexistent term", limit=3)

        assert len(results) > 0
        assert "nonexistent term" in results[0]["title"].lower() or "nonexistent term" in results[0]["abstract"].lower()


# ── 2. Semantic Scholar Client Tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_fetch_papers_success():
    """Test fetch_papers successfully parses raw Semantic Scholar API response."""
    mock_response_data = {
        "data": [
            {
                "paperId": "s2_123456789",
                "title": "Attention Is All You Need",
                "abstract": "The dominant sequence transduction models are based on complex recurrent networks.",
                "url": "https://www.semanticscholar.org/paper/s2_123456789",
                "year": 2017,
                "authors": [
                    {"authorId": "a1", "name": "Ashish Vaswani"},
                    {"authorId": "a2", "name": "Noam Shazeer"}
                ]
            }
        ]
    }

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        results = await fetch_papers(keywords=["transformer", "attention"], limit=5)

        assert len(results) == 1
        record = results[0]

        # Verify exact required keys
        expected_keys = {"paper_id", "title", "abstract", "url", "year", "authors"}
        assert set(record.keys()) == expected_keys

        assert record["paper_id"] == "s2_123456789"
        assert record["title"] == "Attention Is All You Need"
        assert record["year"] == 2017
        assert record["authors"] == ["Ashish Vaswani", "Noam Shazeer"]
        assert record["url"] == "https://www.semanticscholar.org/paper/s2_123456789"


@pytest.mark.asyncio
async def test_fetch_papers_retry_429():
    """Test fetch_papers retries on HTTP 429 rate limit and succeeds on subsequent attempt."""
    mock_429_resp = MagicMock(spec=httpx.Response)
    mock_429_resp.status_code = 429
    mock_429_resp.headers = {"Retry-After": "0.01"}

    mock_200_resp = MagicMock(spec=httpx.Response)
    mock_200_resp.status_code = 200
    mock_200_resp.json.return_value = {
        "data": [
            {
                "paperId": "s2_987654321",
                "title": "Retrieval-Augmented Generation for Knowledge-Intensive Tasks",
                "abstract": "Building RAG architectures.",
                "url": "https://www.semanticscholar.org/paper/s2_987654321",
                "year": 2020,
                "authors": [{"name": "Patrick Lewis"}]
            }
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = [mock_429_resp, mock_200_resp]

        results = await fetch_papers(keywords="RAG architecture", max_retries=2)

        assert mock_get.call_count == 2
        assert len(results) == 1
        assert results[0]["paper_id"] == "s2_987654321"


@pytest.mark.asyncio
async def test_fetch_papers_fallback_on_error():
    """Test fetch_papers gracefully returns fallback records when request repeatedly fails."""
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.HTTPStatusError("500 Internal Server Error", request=MagicMock(), response=MagicMock(status_code=500))

        results = await fetch_papers(keywords="generative ai", max_retries=1)

        assert len(results) > 0
        record = results[0]
        expected_keys = {"paper_id", "title", "abstract", "url", "year", "authors"}
        assert set(record.keys()) == expected_keys
        assert "Generative Ai" in record["title"] or "generative ai" in record["abstract"]


@pytest.mark.asyncio
async def test_fetch_papers_empty_response_fallback():
    """Test fetch_papers returns fallback records when API returns empty data array."""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"data": []}

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        results = await fetch_papers(keywords="unknown query", limit=2)

        assert len(results) > 0
        assert "unknown query" in results[0]["title"].lower() or "unknown query" in results[0]["abstract"].lower()
