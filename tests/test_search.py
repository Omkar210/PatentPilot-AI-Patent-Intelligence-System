"""
tests/test_search.py — Unit Tests for Stage 3 Search Agent Node
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

from state import PatentPilotState
from agents.search import (
    search_agent_node,
    search_agent_node_sync,
    _sanitize_keywords,
    DEFAULT_SEARCH_KEYWORDS,
)


@pytest.mark.asyncio
async def test_search_agent_node_success():
    """Test successful concurrent execution of PatentsView and Semantic Scholar searches."""
    mock_patents = [
        {
            "patent_id": "US10000001B2",
            "title": "Autonomous Driving AI System",
            "abstract": "A machine learning system for vehicle steering.",
            "inventors": ["Alice Smith"],
            "ipc_codes": ["G06N 3/08"],
            "pdf_url": "https://patentimages.storage.googleapis.com/pages/US10000001B2.pdf",
        }
    ]
    mock_papers = [
        {
            "paper_id": "paper_123",
            "title": "Deep Learning for Autonomous Steering",
            "abstract": "A study on neural network architectures for autonomous vehicles.",
            "url": "https://www.semanticscholar.org/paper/paper_123",
            "year": 2024,
            "authors": ["Bob Jones"],
        }
    ]

    state: PatentPilotState = {
        "user_query": "autonomous vehicle steering",
        "search_keywords": ["autonomous driving", "machine learning"],
    }

    with patch(
        "agents.search.fetch_patents", new_callable=AsyncMock
    ) as mock_fetch_patents, patch(
        "agents.search.fetch_papers", new_callable=AsyncMock
    ) as mock_fetch_papers:
        mock_fetch_patents.return_value = mock_patents
        mock_fetch_papers.return_value = mock_papers

        result = await search_agent_node(state)

        assert "patent_results" in result
        assert "research_papers" in result
        assert result["patent_results"] == mock_patents
        assert result["research_papers"] == mock_papers
        mock_fetch_patents.assert_called_once()
        mock_fetch_papers.assert_called_once()


@pytest.mark.asyncio
async def test_search_agent_node_empty_keywords_fallback():
    """Test handling of state with missing or empty search_keywords."""
    state_empty: PatentPilotState = {"user_query": ""}

    with patch(
        "agents.search.fetch_patents", new_callable=AsyncMock
    ) as mock_fetch_patents, patch(
        "agents.search.fetch_papers", new_callable=AsyncMock
    ) as mock_fetch_papers:
        mock_fetch_patents.return_value = []
        mock_fetch_papers.return_value = []

        result = await search_agent_node(state_empty)

        assert "patent_results" in result
        assert "research_papers" in result
        # Check that default keywords were passed to fetch functions
        args_patents, _ = mock_fetch_patents.call_args
        assert args_patents[0] == DEFAULT_SEARCH_KEYWORDS


@pytest.mark.asyncio
async def test_search_agent_node_user_query_fallback():
    """Test fallback to user_query words when search_keywords is empty but user_query exists."""
    state_query: PatentPilotState = {
        "user_query": "quantum error correction",
        "search_keywords": [],
    }

    with patch(
        "agents.search.fetch_patents", new_callable=AsyncMock
    ) as mock_fetch_patents, patch(
        "agents.search.fetch_papers", new_callable=AsyncMock
    ) as mock_fetch_papers:
        mock_fetch_patents.return_value = []
        mock_fetch_papers.return_value = []

        await search_agent_node(state_query)

        args_patents, _ = mock_fetch_patents.call_args
        assert args_patents[0] == ["quantum", "error", "correction"]


@pytest.mark.asyncio
async def test_search_agent_node_partial_failure_patents():
    """Test partial failure where PatentsView fails with exception while Semantic Scholar succeeds."""
    mock_papers = [
        {
            "paper_id": "paper_456",
            "title": "Quantum Error Correction Survey",
            "abstract": "Survey of quantum error mitigation.",
            "url": "https://www.semanticscholar.org/paper/paper_456",
            "year": 2025,
            "authors": ["Charlie Brown"],
        }
    ]

    state: PatentPilotState = {"search_keywords": ["quantum computing"]}

    with patch(
        "agents.search.fetch_patents", new_callable=AsyncMock
    ) as mock_fetch_patents, patch(
        "agents.search.fetch_papers", new_callable=AsyncMock
    ) as mock_fetch_papers:
        mock_fetch_patents.side_effect = RuntimeError("PatentsView API connection error")
        mock_fetch_papers.return_value = mock_papers

        result = await search_agent_node(state)

        assert "patent_results" in result
        assert "research_papers" in result
        assert len(result["patent_results"]) > 0  # Fallback patents generated
        assert result["research_papers"] == mock_papers


@pytest.mark.asyncio
async def test_search_agent_node_timeout_handling():
    """Test handling when concurrent API queries exceed timeout threshold."""

    async def slow_fetch(*args, **kwargs):
        await asyncio.sleep(5.0)
        return []

    state: PatentPilotState = {"search_keywords": ["computer vision"]}

    with patch("agents.search.fetch_patents", side_effect=slow_fetch), patch(
        "agents.search.fetch_papers", side_effect=slow_fetch
    ):
        result = await search_agent_node(state, timeout=0.05)

        assert "patent_results" in result
        assert "research_papers" in result
        assert len(result["patent_results"]) > 0  # Fallback patents
        assert len(result["research_papers"]) > 0  # Fallback papers


def test_search_agent_node_sync_wrapper():
    """Test synchronous wrapper search_agent_node_sync."""
    state: PatentPilotState = {"search_keywords": ["neural network"]}

    with patch(
        "agents.search.fetch_patents", new_callable=AsyncMock
    ) as mock_fetch_patents, patch(
        "agents.search.fetch_papers", new_callable=AsyncMock
    ) as mock_fetch_papers:
        mock_fetch_patents.return_value = [{"patent_id": "US11111111B2"}]
        mock_fetch_papers.return_value = [{"paper_id": "s2_111"}]

        result = search_agent_node_sync(state)

        assert result["patent_results"] == [{"patent_id": "US11111111B2"}]
        assert result["research_papers"] == [{"paper_id": "s2_111"}]
