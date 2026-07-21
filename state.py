"""
state.py — PatentPilot AI Shared State

Defines PatentPilotState, the single TypedDict that flows through
every node of the 11-stage LangGraph pipeline.  Every agent function
accepts and returns a *partial* PatentPilotState — only the keys it
reads and writes need to be present.

Stage → Key mapping
───────────────────
1.  user_query          (input from API)
2.  search_keywords     (Planner agent output)
3.  patent_results      (Search agent — PatentsView)
    research_papers     (Search agent — Semantic Scholar)
4.  raw_documents       (Document Processing agent)
5.  technical_entities  (Entity Extraction agent)
6.  embeddings_ready    (Vector Search agent flag)
    similarity_scores   (Vector Search agent results)
7.  knowledge_graph_id  (Knowledge Graph agent)
8.  prior_art           (Similarity & Prior Art agent)
9.  novelty_score       (Novelty Assessment agent)
    novelty_explanation (Novelty Assessment agent)
10. report              (Report Generation agent)
11. approval_status     (Human Approval node)
    approval_feedback   (Human Approval node)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class PatentPilotState(TypedDict, total=False):
    # ── Stage 1: User Input ────────────────────────────────────────────
    user_query: str
    """The raw natural-language query submitted by the user."""

    # ── Stage 2: Planner Agent ────────────────────────────────────────
    search_keywords: List[str]
    """3-6 focused search keywords extracted from user_query."""

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

    # ── Stage 4: Document Processing ─────────────────────────────────
    raw_documents: List[Dict[str, Any]]
    """
    Extracted/cleaned text per source document.
    Keys: source_id, source_type (patent|paper), text, extraction_method
    """

    # ── Stage 5: Entity Extraction ────────────────────────────────────
    technical_entities: List[Dict[str, Any]]
    """
    Structured entities extracted from raw_documents via LLM.
    Keys: source_id, algorithms, datasets, frameworks,
          inventors, ipc_codes, keywords
    """

    # ── Stage 6: Vector Search (ChromaDB) ────────────────────────────
    embeddings_ready: bool
    """True once raw_documents have been embedded and added to ChromaDB."""

    similarity_scores: List[Dict[str, Any]]
    """
    Top-k nearest-neighbor results from ChromaDB query.
    Keys: source_id, text_snippet, distance, similarity
    """

    # ── Stage 7: Knowledge Graph (Neo4j) ─────────────────────────────
    knowledge_graph_id: Optional[str]
    """Identifier for the graph context created in Neo4j for this run."""

    # ── Stage 8: Similarity & Prior Art ──────────────────────────────
    prior_art: List[Dict[str, Any]]
    """
    Documents flagged as prior art (similarity >= threshold).
    Keys: source_id, title, similarity, text_snippet, source_type
    """

    # ── Stage 9: Novelty Assessment ───────────────────────────────────
    novelty_score: Optional[int]
    """Integer 0-100 indicating the invention's degree of novelty."""

    novelty_explanation: Optional[str]
    """
    LLM-generated explanation citing specific prior art overlap.
    """

    # ── Stage 10: Report Generation ───────────────────────────────────
    report: Optional[Dict[str, Any]]
    """
    Full assembled report dict.
    Keys: query, keywords, novelty_score, novelty_explanation,
          prior_art, technical_entities, patent_count,
          paper_count, generated_at
    """

    # ── Stage 11: Human Approval ──────────────────────────────────────
    approval_status: Optional[str]
    """One of: 'pending' | 'approved' | 'rejected' | 're-run'"""

    approval_feedback: Optional[str]
    """Optional free-text feedback from the human reviewer."""
