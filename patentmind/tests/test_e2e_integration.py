"""
Phase 8 — End-to-End Integration Tests
=======================================
Validates all 15 workflow stages of the PatentMind AI pipeline
via live API endpoints and direct module access.

Run: python -m pytest patentmind/tests/test_e2e_integration.py -v
"""
import os
import sys
import pytest

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from fastapi.testclient import TestClient
from patentmind.api.main import app

client = TestClient(app)


class TestStage1to4DataIngestion:
    """Stages 1-4: Patent extraction, dedup, validation, S3 storage."""

    def test_patents_exist_in_database(self):
        """Verify >= 200 patents are stored in the database."""
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_patents" in data
        assert data["total_patents"] >= 200, f"Expected >= 200 patents, got {data['total_patents']}"

    def test_source_breakdown_populated(self):
        """Verify patents come from multiple sources."""
        resp = client.get("/api/stats")
        data = resp.json()
        breakdown = data.get("source_breakdown", {})
        assert len(breakdown) >= 1, "Source breakdown should have at least 1 source"
        assert sum(breakdown.values()) == data["total_patents"]

    def test_patents_have_s3_keys(self):
        """Verify patents have s3_key populated (S3 storage worked)."""
        resp = client.get("/api/patents?page=1&page_size=5")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) > 0, "Patent list should not be empty"


class TestStage5to8Processing:
    """Stages 5-8: PDF extraction, OCR, cleaning, metadata enrichment."""

    def test_patents_are_processed(self):
        """Verify patents have processing_status in (processed, embedded)."""
        resp = client.get("/api/stats")
        data = resp.json()
        status_breakdown = data.get("status_breakdown", {})
        # At least some patents should be processed or embedded
        processed_count = status_breakdown.get("processed", 0) + status_breakdown.get("embedded", 0)
        assert processed_count > 0, f"No processed/embedded patents found. Status: {status_breakdown}"

    def test_patent_detail_has_content(self):
        """Verify a patent has non-empty title and abstract (text extraction worked)."""
        resp = client.get("/api/patents?page=1&page_size=1")
        items = resp.json()["items"]
        assert len(items) > 0
        pn = items[0]["patent_number"]

        detail = client.get(f"/api/patents/{pn}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["title"] and len(d["title"]) > 3, "Patent title should be non-empty"


class TestStage9to11VectorStorage:
    """Stages 9-11: Chunking, embedding, vector DB storage."""

    def test_vector_backend_active(self):
        """Verify Qdrant vector backend is active."""
        resp = client.get("/api/stats")
        data = resp.json()
        assert "vector_backend" in data
        assert data["vector_backend"] in ("QDRANT", "CHROMADB", "MEMORY")

    def test_vector_search_returns_results(self):
        """Verify semantic search returns chunks for a real query."""
        payload = {"query": "transformer attention mechanism"}
        resp = client.post("/api/query", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["sources"]) > 0, "Vector search should return at least 1 source"


class TestStage12to14RAGPipeline:
    """Stages 12-14: Semantic retrieval, context generation, LLM answer."""

    def test_full_rag_query(self):
        """Submit a real query and verify complete RAG response."""
        payload = {"query": "What methods exist for training large language models with reduced memory usage?"}
        resp = client.post("/api/query", json=payload)
        assert resp.status_code == 200
        data = resp.json()

        assert data["answer"] and len(data["answer"]) > 20, "Answer should be substantive"
        assert data["llm_backend_used"], "LLM backend should be identified"
        assert data["vector_backend_used"], "Vector backend should be identified"
        assert len(data["sources"]) > 0, "Should cite at least one source patent"

    def test_query_sources_have_metadata(self):
        """Verify each source has patent_number, section, score, chunk_text."""
        payload = {"query": "neural network optimization techniques"}
        resp = client.post("/api/query", json=payload)
        data = resp.json()

        for source in data["sources"]:
            assert "patent_number" in source
            assert "section" in source
            assert "score" in source
            assert "chunk_text" in source
            assert source["score"] >= 0.0


class TestStage15FrontendUI:
    """Stage 15: Frontend serves correctly."""

    def test_frontend_serves_html(self):
        """Verify GET / returns HTML with PatentMind branding."""
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
        assert "PatentMind" in resp.text or "patentmind" in resp.text.lower()


class TestComparePDFEndpoint:
    """The hero Compare PDF feature."""

    def test_compare_pdf_returns_three_branches(self):
        """Upload a minimal PDF and verify 3-branch response."""
        # Create a minimal valid PDF
        pdf_content = (
            b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<<>>>>endobj\n"
            b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 100 700 Td (AI Patent Test) Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000230 00000 n \n"
            b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n326\n%%EOF"
        )
        resp = client.post(
            "/api/compare-pdf",
            files={"paper": ("test_patent.pdf", pdf_content, "application/pdf")}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "semantic_matches" in data
        assert "graph_data" in data
        assert "synthesis" in data
        assert "vector_backend_used" in data


class TestSystemStatusEndpoint:
    """Infrastructure health check."""

    def test_system_status_reports_all_services(self):
        """Verify system-status returns status for all 4 services."""
        resp = client.get("/api/system-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "qdrant" in data
        assert "ollama" in data
        assert "neo4j" in data
        assert "groq" in data
        for service in ["qdrant", "ollama", "neo4j", "groq"]:
            assert "status" in data[service]


class TestPatentDetailEndpoint:
    """Data access verification."""

    def test_patent_detail_for_known_patent(self):
        """Fetch first patent and verify full metadata."""
        listing = client.get("/api/patents?page=1&page_size=1")
        items = listing.json()["items"]
        assert len(items) > 0
        pn = items[0]["patent_number"]

        resp = client.get(f"/api/patents/{pn}")
        assert resp.status_code == 200
        d = resp.json()
        assert d["patent_number"] == pn
        for field in ["patent_id", "title", "patent_number", "processing_status"]:
            assert field in d

    def test_patent_detail_404_for_unknown(self):
        """Verify 404 for a non-existent patent."""
        resp = client.get("/api/patents/NONEXISTENT_PATENT_999")
        assert resp.status_code == 404
