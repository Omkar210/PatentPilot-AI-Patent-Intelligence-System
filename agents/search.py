"""
agents/search.py — Stage 3: Search Agent Node

Concurrently queries PatentsView (USPTO patents) and Semantic Scholar (research papers)
using search keywords produced by Stage 2 (Planner agent). Returns updated PatentPilotState dict.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Union

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

    # Fallback to user_query if search_keywords absent or empty
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
        logger.warning(
            f"PatentsView search failed with exception: {patents_res}. Using fallback data."
        )
        patent_results = _get_fallback_patents(keywords, limit)
    elif isinstance(patents_res, list):
        patent_results = patents_res
    else:
        patent_results = _get_fallback_patents(keywords, limit)

    # Process research paper results
    if isinstance(papers_res, Exception):
        logger.warning(
            f"Semantic Scholar search failed with exception: {papers_res}. Using fallback data."
        )
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
        import nest_asyncio

        nest_asyncio.apply()
        return loop.run_until_complete(
            search_agent_node(state, limit=limit, timeout=timeout)
        )
    else:
        return asyncio.run(search_agent_node(state, limit=limit, timeout=timeout))
