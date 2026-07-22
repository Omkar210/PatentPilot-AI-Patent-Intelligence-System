"""
tests/test_phase4_intelligence.py — Unit & Integration Tests for Phase 4 Intelligence Agents

Tests:
1. Entity Extraction node (agents/entity_extraction.py).
2. Similarity & Prior Art node threshold filtering (agents/similarity.py).
3. Novelty Assessment node scoring (0-100) & explanation (agents/novelty.py).
4. End-to-end execution of full graph on multiple sample queries.
"""

import pytest
from agents.entity_extraction import extract_entities_from_doc, entity_extraction_agent_node
from agents.similarity import similarity_prior_art_agent_node
from agents.novelty import novelty_assessment_agent_node
from graph import graph


def test_entity_extraction_node():
    doc = {
        "source_id": "US-TEST-ENT1",
        "text": "A deep learning neural network using PyTorch framework for computer vision and image classification.",
        "source_type": "patent"
    }

    res = extract_entities_from_doc(doc)
    assert res["source_id"] == "US-TEST-ENT1"
    assert "algorithms" in res
    assert "frameworks" in res
    assert "keywords" in res


def test_similarity_prior_art_threshold():
    state = {
        "similarity_scores": [
            {
                "source_id": "US101",
                "similarity": 0.82,
                "text_snippet": "High similarity prior art snippet",
                "title": "Patent 101"
            },
            {
                "source_id": "US102",
                "similarity": 0.60,
                "text_snippet": "Low similarity snippet",
                "title": "Patent 102"
            }
        ]
    }

    update = similarity_prior_art_agent_node(state)
    assert "prior_art" in update
    assert len(update["prior_art"]) == 1
    assert update["prior_art"][0]["source_id"] == "US101"
    assert update["prior_art"][0]["similarity"] == 0.82


def test_novelty_assessment_node():
    state = {
        "user_query": "AI multi-agent patent novelty system using transformer architectures",
        "prior_art": [
            {
                "source_id": "US201",
                "similarity": 0.88,
                "text_snippet": "Multi-agent system for legal patent document analysis using transformers.",
                "title": "Patent System 201"
            }
        ]
    }

    update = novelty_assessment_agent_node(state)
    assert "novelty_score" in update
    assert "novelty_explanation" in update
    assert 0 <= update["novelty_score"] <= 100
    assert len(update["novelty_explanation"]) > 20


def test_e2e_graph_sanity_check_queries():
    sample_queries = [
        "retrieval augmented generation system with vector database",
        "quantum computing neural network for drug discovery"
    ]

    for q in sample_queries:
        result = graph.invoke({"user_query": q})
        assert result.get("search_keywords") is not None
        assert isinstance(result.get("technical_entities"), list)
        assert result.get("embeddings_ready") is True
        assert isinstance(result.get("similarity_scores"), list)
        assert isinstance(result.get("prior_art"), list)
        assert result.get("novelty_score") is not None
        assert 0 <= result.get("novelty_score") <= 100
        assert result.get("novelty_explanation") is not None
