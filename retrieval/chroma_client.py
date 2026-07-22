"""
retrieval/chroma_client.py — Embedded ChromaDB Vector Client for PatentPilot AI

Uses chromadb.PersistentClient with sentence-transformers ('all-MiniLM-L6-v2')
to embed raw_documents text into the 'patent_documents' collection.
"""

import os
import logging
from typing import Any, Dict, List, Optional
import chromadb
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CHROMA_PERSIST_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_data")
COLLECTION_NAME = "patent_documents"
MODEL_NAME = "all-MiniLM-L6-v2"

_chroma_client: Optional[chromadb.PersistentClient] = None
_embed_model: Optional[SentenceTransformer] = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(CHROMA_PERSIST_PATH, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(path=CHROMA_PERSIST_PATH)
    return _chroma_client


def get_embed_model() -> SentenceTransformer:
    global _embed_model
    if _embed_model is None:
        logger.info(f"Loading sentence-transformer model '{MODEL_NAME}'...")
        _embed_model = SentenceTransformer(MODEL_NAME)
    return _embed_model


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


def add_documents(documents: List[Dict[str, Any]]) -> int:
    """
    Embeds raw_documents text and adds them to ChromaDB collection.
    Each doc dict should contain: source_id, text, source_type (optional)
    """
    if not documents:
        return 0

    collection = get_collection()
    model = get_embed_model()

    ids = []
    texts = []
    metadatas = []

    for doc in documents:
        source_id = str(doc.get("source_id") or doc.get("patent_id") or doc.get("id") or "").strip()
        text = str(doc.get("text") or doc.get("abstract") or "").strip()
        
        if not source_id or not text:
            continue

        ids.append(source_id)
        # Truncate text if excessively long for MiniLM context window
        texts.append(text[:2000])
        metadatas.append({
            "source_id": source_id,
            "source_type": str(doc.get("source_type") or "patent"),
            "title": str(doc.get("title") or "")[:200]
        })

    if not texts:
        return 0

    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas
    )

    logger.info(f"Upserted {len(ids)} documents into ChromaDB collection '{COLLECTION_NAME}'")
    return len(ids)


def query_similar(query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Queries ChromaDB collection with user_query embedding for top-k semantically similar results.
    Converts cosine distance to similarity score (similarity = 1.0 - distance).
    """
    if not query_text or not query_text.strip():
        return []

    collection = get_collection()
    if collection.count() == 0:
        return []

    model = get_embed_model()
    query_embedding = model.encode([query_text], show_progress_bar=False).tolist()

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k, collection.count()),
        include=["documents", "metadatas", "distances"]
    )

    formatted_results = []
    if results and "ids" in results and results["ids"]:
        ids_list = results["ids"][0]
        docs_list = results.get("documents", [[]])[0]
        meta_list = results.get("metadatas", [[]])[0]
        dist_list = results.get("distances", [[]])[0]

        for i in range(len(ids_list)):
            source_id = ids_list[i]
            snippet = docs_list[i] if i < len(docs_list) else ""
            meta = meta_list[i] if i < len(meta_list) else {}
            dist = float(dist_list[i]) if i < len(dist_list) else 1.0

            # Convert distance to similarity (ChromaDB default L2/cosine distance)
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0) if dist > 1.0 else 1.0 - dist))

            formatted_results.append({
                "source_id": source_id,
                "text_snippet": snippet[:500],
                "distance": round(dist, 4),
                "similarity": round(similarity, 4),
                "title": meta.get("title", ""),
                "source_type": meta.get("source_type", "patent")
            })

    return formatted_results
