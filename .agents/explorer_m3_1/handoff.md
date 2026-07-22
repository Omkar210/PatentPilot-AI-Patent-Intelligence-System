# Milestone 3 Handoff Report: Search Agent Node (`agents/search.py`)

## 1. Observation

Direct observations from inspecting the codebase:

### 1.1 State Schema (`state.py`)
- Lines 43–54:
  ```python
  # ── Stage 3: Search Agents (parallel) ────────────────────────────
  patent_results: List[Dict[str, Any]]
  """
  List of patent records from PatentsView API.
  Keys: patent_id, title, abstract, inventors, ipc_codes, pdf_url
  """

  research_papers: List[Dict[str, Any]]
  """
  List of research paper records from Semantic Scholar API.
  Keys: paper_id, title, abstract, url, year, authors
  """
  ```
- Lines 39–41:
  ```python
  # ── Stage 2: Planner Agent ────────────────────────────────────────
  search_keywords: List[str]
  """3-6 focused search keywords extracted from user_query."""
  ```

### 1.2 Ingestion Clients (`ingestion/patentsview.py` and `ingestion/semantic_scholar.py`)
- `ingestion/patentsview.py` (Line 106):
  ```python
  async def fetch_patents(
      keywords: Union[str, List[str]],
      limit: int = 10,
      api_key: Optional[str] = None,
      max_retries: int = 3,
  ) -> List[Dict[str, Any]]
  ```
  Returns `List[Dict[str, Any]]` with keys: `patent_id`, `title`, `abstract`, `inventors`, `ipc_codes`, `pdf_url`. Fallback generator `_get_fallback_patents(keywords, limit)` is available.

- `ingestion/semantic_scholar.py` (Line 91):
  ```python
  async def fetch_papers(
      keywords: Union[str, List[str]],
      limit: int = 10,
      api_key: Optional[str] = None,
      max_retries: int = 3,
  ) -> List[Dict[str, Any]]
  ```
  Returns `List[Dict[str, Any]]` with keys: `paper_id`, `title`, `abstract`, `url`, `year`, `authors`. Fallback generator `_get_fallback_papers(keywords, limit)` is available.

### 1.3 Graph Wiring (`graph.py`)
- Line 34:
  ```python
  def search_agent_node(state: PatentPilotState) -> Dict[str, Any]:
      """Stage 3: Search agents (parallel) - PatentsView + Semantic Scholar."""
      return {
          "patent_results": state.get("patent_results", []),
          "research_papers": state.get("research_papers", []),
      }
  ```
- Line 98: `builder.add_node("search", search_agent_node)`
- Line 111: `builder.add_edge("planner", "search")`
- Line 112: `builder.add_edge("search", "document_processing")`

### 1.4 Test Suite Execution
- Executed `.\venv\Scripts\python.exe -m pytest tests/test_planner.py tests/test_ingestion_clients.py` via `run_command`. Result: `17 passed in 4.30s`.

---

## 2. Logic Chain

1. **Input Extraction & Fallback**:
   - `search_agent_node` receives `state: PatentPilotState`.
   - Reads `search_keywords` from `state.get("search_keywords", [])`.
   - If `search_keywords` is missing, empty, or contains only whitespace strings, check `state.get("user_query")`. If present, extract tokens or fallback to standard keywords `["artificial intelligence", "patent intelligence", "prior art"]`. This ensures search functions receive valid keywords.

2. **Parallel Concurrency via `asyncio.gather`**:
   - Stage 3 requires parallel execution of PatentsView and Semantic Scholar searches.
   - `asyncio.gather(fetch_patents(keywords, limit=limit), fetch_papers(keywords, limit=limit), return_exceptions=True)` executes both network coroutines concurrently.
   - Setting `return_exceptions=True` prevents an exception in one client from cancelling or crashing the other client.

3. **Timeout & Exception Resilience**:
   - Wrap `asyncio.gather` in `asyncio.wait_for(..., timeout=30.0)`.
   - If `asyncio.TimeoutError` is raised, log an error and use `_get_fallback_patents(keywords, limit)` and `_get_fallback_papers(keywords, limit)`.
   - Inspect elements returned by `asyncio.gather`:
     - If `isinstance(patents_res, Exception)`, log warning and replace with `_get_fallback_patents(keywords, limit)`.
     - If `isinstance(papers_res, Exception)`, log warning and replace with `_get_fallback_papers(keywords, limit)`.

4. **Sync / Async LangGraph Compatibility**:
   - LangGraph `StateGraph` supports both `async def` nodes and standard `def` nodes.
   - Provide primary `async def search_agent_node(state: PatentPilotState) -> Dict[str, Any]` for asynchronous pipelines (`graph.ainvoke`).
   - Provide `def search_agent_node_sync(state: PatentPilotState) -> Dict[str, Any]` (or handle synchronous invocation safely) to support synchronous invocation (`graph.invoke`) without raising `RuntimeError: Event loop is already running`.

5. **State Schema Compliance**:
   - Return dictionary containing strictly:
     ```python
     {
         "patent_results": patent_results,
         "research_papers": research_papers,
     }
     ```
   - Each patent dict conforms to `patent_id`, `title`, `abstract`, `inventors`, `ipc_codes`, `pdf_url`.
   - Each paper dict conforms to `paper_id`, `title`, `abstract`, `url`, `year`, `authors`.

---

## 3. Caveats

- **API Rate Limits & Keys**: PatentsView and Semantic Scholar APIs can rate-limit requests (HTTP 429) or time out without API keys. Ingestion modules already handle HTTP 429 with exponential backoff and fallback, so `search_agent_node` must handle exceptions gracefully as a secondary defense layer.
- **Async Execution Contexts**: In synchronous test harnesses or CLI scripts calling `graph.invoke()`, running an `async def` node requires event loop management. Providing a sync wrapper `search_agent_node_sync` ensures seamless testing and compatibility across sync and async contexts.

---

## 4. Conclusion & Proposed Implementation

### 4.1 Proposed Implementation: `agents/search.py`

```python
"""
agents/search.py — Stage 3: Search Agent Node

Concurrently queries PatentsView (USPTO patents) and Semantic Scholar (research papers)
using search keywords produced by Stage 2 (Planner agent). Returns updated PatentPilotState dict.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Union

from state import PatentPilotState
from ingestion.patentsview import fetch_patents, _get_fallback_patents
from ingestion.semantic_scholar import fetch_papers, _get_fallback_papers

logger = logging.getLogger(__name__)

DEFAULT_SEARCH_KEYWORDS = [
    "artificial intelligence",
    "patent intelligence",
    "prior art",
]


def _sanitize_keywords(state: PatentPilotState) -> List[str]:
    """Extracts and sanitizes search_keywords from state, falling back if empty."""
    raw_keywords = state.get("search_keywords", []) if state else []
    
    clean_kws: List[str] = []
    if isinstance(raw_keywords, list):
        for kw in raw_keywords:
            if kw and isinstance(kw, str) and kw.strip():
                clean_kws.append(kw.strip())
    elif isinstance(raw_keywords, str) and raw_keywords.strip():
        clean_kws = [k.strip() for k in raw_keywords.split(",") if k.strip()]

    if clean_kws:
        return clean_kws

    # Fallback to user_query if keywords absent
    user_query = state.get("user_query", "") if state else ""
    if user_query and isinstance(user_query, str) and user_query.strip():
        words = [w.strip() for w in user_query.split() if len(w.strip()) > 2]
        if words:
            return words[:4]

    return list(DEFAULT_SEARCH_KEYWORDS)


async def search_agent_node(
    state: PatentPilotState, limit: int = 10, timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Stage 3: Asynchronous Search Agent node for LangGraph pipeline.

    Reads `state['search_keywords']`, concurrently fetches patent records and
    research papers, and returns updated state dictionary:
    {
        "patent_results": List[Dict[str, Any]],
        "research_papers": List[Dict[str, Any]]
    }
    """
    keywords = _sanitize_keywords(state)
    logger.info(f"Search Agent Node executing concurrent query with keywords: {keywords}")

    patent_task = fetch_patents(keywords, limit=limit)
    paper_task = fetch_papers(keywords, limit=limit)

    try:
        results = await asyncio.wait_for(
            asyncio.gather(patent_task, paper_task, return_exceptions=True),
            timeout=timeout,
        )
        patents_res, papers_res = results
    except asyncio.TimeoutError:
        logger.error(f"Search Agent Node timed out after {timeout} seconds.")
        patents_res = _get_fallback_patents(keywords, limit)
        papers_res = _get_fallback_papers(keywords, limit)

    # Process patent results
    if isinstance(patents_res, Exception):
        logger.warning(f"PatentsView search failed with exception: {patents_res}. Using fallback data.")
        patent_results = _get_fallback_patents(keywords, limit)
    elif isinstance(patents_res, list):
        patent_results = patents_res
    else:
        patent_results = _get_fallback_patents(keywords, limit)

    # Process research paper results
    if isinstance(papers_res, Exception):
        logger.warning(f"Semantic Scholar search failed with exception: {papers_res}. Using fallback data.")
        research_papers = _get_fallback_papers(keywords, limit)
    elif isinstance(papers_res, list):
        research_papers = papers_res
    else:
        research_papers = _get_fallback_papers(keywords, limit)

    return {
        "patent_results": patent_results,
        "research_papers": research_papers,
    }


def search_agent_node_sync(
    state: PatentPilotState, limit: int = 10, timeout: float = 30.0
) -> Dict[str, Any]:
    """
    Synchronous wrapper for search_agent_node for compatibility with
    synchronous LangGraph execution (graph.invoke) or non-async callers.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # In active event loop context
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(search_agent_node(state, limit=limit, timeout=timeout))
    else:
        return asyncio.run(search_agent_node(state, limit=limit, timeout=timeout))
```

---

### 4.2 Proposed Test Suite: `tests/test_search.py`

```python
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

    with patch("agents.search.fetch_patents", new_callable=AsyncMock) as mock_fetch_patents, \
         patch("agents.search.fetch_papers", new_callable=AsyncMock) as mock_fetch_papers:
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

    with patch("agents.search.fetch_patents", new_callable=AsyncMock) as mock_fetch_patents, \
         patch("agents.search.fetch_papers", new_callable=AsyncMock) as mock_fetch_papers:
        mock_fetch_patents.return_value = []
        mock_fetch_papers.return_value = []

        result = await search_agent_node(state_empty)

        assert "patent_results" in result
        assert "research_papers" in result
        # Check that default keywords were passed to fetch functions
        args_patents, _ = mock_fetch_patents.call_args
        assert args_patents[0] == DEFAULT_SEARCH_KEYWORDS


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

    with patch("agents.search.fetch_patents", new_callable=AsyncMock) as mock_fetch_patents, \
         patch("agents.search.fetch_papers", new_callable=AsyncMock) as mock_fetch_papers:
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

    with patch("agents.search.fetch_patents", side_effect=slow_fetch), \
         patch("agents.search.fetch_papers", side_effect=slow_fetch):

        result = await search_agent_node(state, timeout=0.05)

        assert "patent_results" in result
        assert "research_papers" in result
        assert len(result["patent_results"]) > 0  # Fallback patents
        assert len(result["research_papers"]) > 0  # Fallback papers


def test_search_agent_node_sync_wrapper():
    """Test synchronous wrapper search_agent_node_sync."""
    state: PatentPilotState = {"search_keywords": ["neural network"]}

    with patch("agents.search.fetch_patents", new_callable=AsyncMock) as mock_fetch_patents, \
         patch("agents.search.fetch_papers", new_callable=AsyncMock) as mock_fetch_papers:
        mock_fetch_patents.return_value = [{"patent_id": "US11111111B2"}]
        mock_fetch_papers.return_value = [{"paper_id": "s2_111"}]

        result = search_agent_node_sync(state)

        assert result["patent_results"] == [{"patent_id": "US11111111B2"}]
        assert result["research_papers"] == [{"paper_id": "s2_111"}]
```

---

## 5. Verification Method

1. **Codebase Inspection**:
   - Confirm `agents/search.py` imports `PatentPilotState` from `state.py`, `fetch_patents` from `ingestion/patentsview.py`, and `fetch_papers` from `ingestion/semantic_scholar.py`.
2. **Execute Unit Tests**:
   - Run: `.\venv\Scripts\python.exe -m pytest tests/test_search.py`
3. **Run Full Test Suite**:
   - Run: `.\venv\Scripts\python.exe -m pytest tests/`
4. **LangGraph Pipeline Integration**:
   - Update `graph.py` to import `search_agent_node` from `agents.search`.
   - Run `.\venv\Scripts\python.exe graph.py` to confirm full 11-stage graph compilation and execution.
