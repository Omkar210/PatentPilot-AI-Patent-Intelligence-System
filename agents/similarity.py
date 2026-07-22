"""
agents/similarity.py — Stage 8: Similarity & Prior Art Agent Node

Pure computation node (no LLM call):
Reads similarity_scores from ChromaDB vector search (which already computes
similarity = 1 - cosine_distance). Flags any document with similarity >= 0.75
as prior_art with text snippet.
"""

import logging
from typing import Any, Dict, List
from state import PatentPilotState

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.75


def similarity_prior_art_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Similarity & Prior Art node accepting and returning partial PatentPilotState.
    """
    scores = state.get("similarity_scores") or []
    prior_art_list = []

    for item in scores:
        similarity = float(item.get("similarity") or 0.0)
        if similarity >= SIMILARITY_THRESHOLD:
            prior_art_list.append({
                "source_id": str(item.get("source_id") or ""),
                "parent_id": str(item.get("parent_id") or ""),
                "title": str(item.get("title") or ""),
                "similarity": round(similarity, 4),
                "text_snippet": str(item.get("text_snippet") or "")[:1000],
                "source_type": str(item.get("source_type") or "patent")
            })

    logger.info(
        f"Similarity Agent: Processed {len(scores)} scores, "
        f"flagged {len(prior_art_list)} prior art documents above threshold {SIMILARITY_THRESHOLD}"
    )

    return {"prior_art": prior_art_list}
