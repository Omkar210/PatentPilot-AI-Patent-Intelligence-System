"""
agents/vector_search.py — Vector Search Agent Node for PatentPilot AI

Stage 6 of the 11-stage pipeline:
1. Embeds current raw_documents and adds them to ChromaDB collection.
2. Queries ChromaDB for top 5 semantically similar documents to state["user_query"].
3. Updates embeddings_ready=True and populates similarity_scores in PatentPilotState.
"""

from typing import Any, Dict
from state import PatentPilotState
from retrieval.chroma_client import add_documents, query_similar


def vector_search_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """
    Vector search node function accepting and returning partial PatentPilotState dict.
    """
    user_query = str(state.get("user_query") or "").strip()
    raw_docs = state.get("raw_documents") or []

    # If raw_documents exist in state, index them into ChromaDB
    added_count = 0
    if raw_docs:
        added_count = add_documents(raw_docs)

    # Query ChromaDB for top 5 semantically similar results
    similarity_results = []
    if user_query:
        similarity_results = query_similar(query_text=user_query, top_k=5)

    return {
        "embeddings_ready": True,
        "similarity_scores": similarity_results
    }
