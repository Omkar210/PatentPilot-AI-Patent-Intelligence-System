"""
graph.py — PatentPilot AI LangGraph Workflow

Wires the locked 11-stage pipeline in sequence per AGENTS.md:
1.  user_query (FastAPI endpoint entry point)
2.  planner_agent
3.  search_agent
4.  document_processing_agent
5.  entity_extraction_agent
6.  knowledge_graph_agent
7.  vector_search_agent
8.  similarity_prior_art_agent
9.  novelty_assessment_agent
10. report_generation_agent
11. human_approval_node

Every agent function accepts a partial PatentPilotState dict and returns a state dict update.
"""

from typing import Any, Dict
from langgraph.graph import StateGraph, START, END
from state import PatentPilotState

from agents.planner import planner_agent_node
from agents.search import search_agent_node_sync as search_agent_node
from agents.document_processing import document_processing_agent_node
from agents.entity_extraction import entity_extraction_agent_node
from agents.knowledge_graph import knowledge_graph_agent_node
from agents.vector_search import vector_search_agent_node
from agents.similarity import similarity_prior_art_agent_node
from agents.novelty import novelty_assessment_agent_node


# ── Passthrough Stub Nodes for remaining stages ──────────────────────────────

def user_query_node(state: PatentPilotState) -> Dict[str, Any]:
    """Stage 1: User Query submission endpoint entry point."""
    return {"user_query": state.get("user_query", "")}


def report_generation_agent_node(state: PatentPilotState) -> Dict[str, Any]:
    """Stage 10: Report generation agent."""
    return {"report": state.get("report", None)}


def human_approval_node(state: PatentPilotState) -> Dict[str, Any]:
    """Stage 11: Human approval - approve / reject / request re-analysis."""
    return {
        "approval_status": state.get("approval_status", "pending"),
        "approval_feedback": state.get("approval_feedback", None),
    }


# ── Build & Wire the LangGraph Workflow ──────────────────────────────────────

builder = StateGraph(PatentPilotState)

# Add all 11 nodes
builder.add_node("user_query", user_query_node)
builder.add_node("planner", planner_agent_node)
builder.add_node("search", search_agent_node)
builder.add_node("document_processing", document_processing_agent_node)
builder.add_node("entity_extraction", entity_extraction_agent_node)
builder.add_node("knowledge_graph", knowledge_graph_agent_node)
builder.add_node("vector_search", vector_search_agent_node)
builder.add_node("similarity_prior_art", similarity_prior_art_agent_node)
builder.add_node("novelty_assessment", novelty_assessment_agent_node)
builder.add_node("report_generation", report_generation_agent_node)
builder.add_node("human_approval", human_approval_node)

# Wire sequence per locked 11-stage workflow
builder.add_edge(START, "user_query")
builder.add_edge("user_query", "planner")
builder.add_edge("planner", "search")
builder.add_edge("search", "document_processing")
builder.add_edge("document_processing", "entity_extraction")
builder.add_edge("entity_extraction", "knowledge_graph")
builder.add_edge("knowledge_graph", "vector_search")
builder.add_edge("vector_search", "similarity_prior_art")
builder.add_edge("similarity_prior_art", "novelty_assessment")
builder.add_edge("novelty_assessment", "report_generation")
builder.add_edge("report_generation", "human_approval")
builder.add_edge("human_approval", END)

# Compile graph into runnable application
graph = builder.compile()


if __name__ == "__main__":
    test_input = {"user_query": "artificial intelligence patent search"}
    result = graph.invoke(test_input)
    print("\n=== Graph Execution Successful ===")
    print(f"Keywords: {result.get('search_keywords')}")
    print(f"Entities Count: {len(result.get('technical_entities', []))}")
    print(f"Embeddings Ready: {result.get('embeddings_ready')}")
    print(f"Similarity Scores Count: {len(result.get('similarity_scores', []))}")
    print(f"Prior Art Flagged Count: {len(result.get('prior_art', []))}")
    print(f"Novelty Score: {result.get('novelty_score')}")
    print(f"Novelty Explanation: {result.get('novelty_explanation')}")
