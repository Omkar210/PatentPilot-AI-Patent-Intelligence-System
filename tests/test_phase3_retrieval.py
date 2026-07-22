"""
tests/test_phase3_retrieval.py — Unit & Integration Tests for Phase 3 Retrieval Layer

Tests:
1. ChromaDB embedding & similarity search (chroma_client.py & vector_search.py).
2. Neo4j Cypher node/relationship MERGE queries (neo4j_client.py & knowledge_graph.py).
3. NetworkX subgraph extraction (graph_utils.py).
4. End-to-end graph workflow invocation through Stage 7.
"""

import os
import pytest
import networkx as nx

from retrieval.chroma_client import add_documents, query_similar
from agents.vector_search import vector_search_agent_node
from agents.knowledge_graph import knowledge_graph_agent_node
from retrieval.graph_utils import get_patent_subgraph
from graph import graph


def test_chroma_embedding_and_query():
    dummy_docs = [
        {
            "source_id": "US-TEST-P1",
            "text": "Deep learning neural network architecture for image recognition and computer vision.",
            "source_type": "patent",
            "title": "Deep Learning Vision System"
        },
        {
            "source_id": "US-TEST-P2",
            "text": "Autonomous robot navigation using lidar sensors and spatial mapping algorithms.",
            "source_type": "patent",
            "title": "Autonomous Robot Lidar"
        }
    ]

    # Add documents to ChromaDB
    added = add_documents(dummy_docs)
    assert added >= 1

    # Query similar
    results = query_similar("neural network image classification", top_k=2)
    assert len(results) >= 1
    assert "source_id" in results[0]
    assert "similarity" in results[0]


def test_vector_search_agent_node():
    state = {
        "user_query": "deep learning neural network",
        "raw_documents": [
            {
                "source_id": "US-TEST-NODE1",
                "text": "Neural network optimization using gradient descent.",
                "source_type": "patent"
            }
        ]
    }

    update = vector_search_agent_node(state)
    assert update["embeddings_ready"] is True
    assert isinstance(update["similarity_scores"], list)
    assert len(update["similarity_scores"]) >= 1


def test_knowledge_graph_agent_node():
    state = {
        "patent_results": [
            {
                "patent_id": "US10000000B2",
                "title": "COHERENT LADAR SYSTEM",
                "inventors": ["John Marron"],
                "ipc_codes": ["G01S 17/89"]
            }
        ],
        "technical_entities": [
            {
                "source_id": "US10000000B2",
                "algorithms": ["Quadrature Detection", "Heterodyne Mixing"]
            }
        ]
    }

    update = knowledge_graph_agent_node(state)
    assert "knowledge_graph_id" in update
    assert update["knowledge_graph_id"].startswith("kg_run_")


def test_networkx_subgraph_extraction():
    patent_id = "US10000000B2"
    G = get_patent_subgraph(patent_id)
    assert isinstance(G, nx.Graph)
    assert patent_id in G.nodes()


def test_e2e_graph_execution_phase3():
    test_input = {"user_query": "artificial intelligence patent search"}
    result = graph.invoke(test_input)
    assert result["embeddings_ready"] is True
    assert isinstance(result["similarity_scores"], list)
    assert result["knowledge_graph_id"] is not None
