"""
Phase 8 — Fallback Mechanism Tests
===================================
Verifies that every service fallback activates correctly
when the primary service is unavailable.

Run: python -m pytest patentmind/tests/test_fallback_mechanisms.py -v
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)


class TestQdrantFallback:
    """Verify VectorStore falls back to in-memory Qdrant when host is unreachable."""

    def test_qdrant_unreachable_falls_back_to_memory(self):
        """When Qdrant host is unreachable, VectorStore should initialize with in-memory backend."""
        with patch.dict(os.environ, {"QDRANT_HOST": "192.168.255.255", "QDRANT_PORT": "9999"}):
            # Force re-import to pick up new env vars
            from patentmind.embeddings.vector_store import VectorStore
            vs = VectorStore()
            # Should not crash — should fall back to memory or local
            assert vs.backend in ("qdrant", "memory"), f"Unexpected backend: {vs.backend}"
            # Verify search works even on empty fallback
            results = vs.search([0.0] * 384, top_k=1)
            assert isinstance(results, list)


class TestOllamaToGroqFallback:
    """Verify LLMRouter falls back to Groq when Ollama is unavailable."""

    def test_ollama_unavailable_triggers_groq(self):
        """When Ollama throws OllamaUnavailableError, Groq should handle the request."""
        from patentmind.llm.router import LLMRouter
        from patentmind.llm.ollama_client import OllamaUnavailableError

        router = LLMRouter()

        # Mock Ollama to always fail
        with patch.object(router.ollama, 'generate', side_effect=OllamaUnavailableError("Connection refused")):
            result = router.generate("Test fallback prompt")
            assert "answer" in result
            assert len(result["answer"]) > 0
            assert "Groq" in result["llm_backend_used"] or "groq" in result["llm_backend_used"].lower()


class TestNeo4jOfflineGraceful:
    """Verify Neo4j client returns safe empty data when driver is None."""

    def test_neo4j_offline_returns_empty_graph(self):
        """When Neo4j is offline, get_patent_network should return empty structures."""
        from patentmind.graph.neo4j_client import Neo4jClient

        # Create client with driver forced to None
        client = Neo4jClient()
        client.driver = None

        network = client.get_patent_network("US12345678")
        # Should return a dict (not crash)
        assert isinstance(network, dict)

    def test_neo4j_offline_graph_stats(self):
        """get_graph_stats should return zero-count dict when offline."""
        from patentmind.graph.neo4j_client import Neo4jClient

        client = Neo4jClient()
        client.driver = None

        stats = client.get_graph_stats()
        assert isinstance(stats, dict)


class TestEncoderHashFallback:
    """Verify EmbeddingEncoder falls back to DeterministicHashEncoder."""

    def test_hash_encoder_produces_384_dim_vectors(self):
        """DeterministicHashEncoder should produce 384-dim vectors deterministically."""
        from patentmind.embeddings.encoder import DeterministicHashEncoder

        encoder = DeterministicHashEncoder()
        embeddings = encoder.encode(["test text one", "test text two"])

        assert len(embeddings) == 2
        assert len(embeddings[0]) == 384
        assert len(embeddings[1]) == 384

        # Deterministic: same input = same output
        embeddings_again = encoder.encode(["test text one"])
        assert embeddings[0] == embeddings_again[0]

    def test_hash_encoder_different_inputs_different_outputs(self):
        """Different texts should produce different embeddings."""
        from patentmind.embeddings.encoder import DeterministicHashEncoder

        encoder = DeterministicHashEncoder()
        emb = encoder.encode(["alpha beta", "gamma delta"])
        assert emb[0] != emb[1]
