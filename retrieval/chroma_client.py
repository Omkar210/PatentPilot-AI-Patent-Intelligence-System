"""
retrieval/chroma_client.py — Embedded ChromaDB Client with Parent-Child Chunking

Implements Parent-Child Chunking for Patent Intelligence:
- Parent Chunks (~2000 chars): Full section/claim text stored in metadata.
- Child Chunks (~300 chars, 50 overlap): Small vector embeddings in ChromaDB for high-precision search.
"""

import os
import uuid
import logging
from typing import Any, Dict, List, Optional, Tuple
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

CHROMA_PERSIST_PATH = os.getenv("CHROMA_PERSIST_PATH", "./chroma_data")
COLLECTION_NAME = "patent_documents"
MODEL_NAME = "all-MiniLM-L6-v2"

_chroma_client: Optional[chromadb.PersistentClient] = None
_embed_model: Optional[SentenceTransformer] = None

# Parent and Child Text Splitters
parent_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=200,
    separators=["\n\nClaim ", "\n\n", "\n", ". ", " "]
)

child_splitter = RecursiveCharacterTextSplitter(
    chunk_size=300,
    chunk_overlap=50,
    separators=["\n\n", "\n", ". ", "; ", " "]
)


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


def create_parent_child_chunks(source_id: str, text: str, source_type: str = "patent", title: str = "") -> Tuple[List[str], List[str], List[Dict[str, Any]]]:
    """
    Splits full text into Parent Chunks (~2000 chars) and Child Chunks (~300 chars).
    Returns (child_ids, child_texts, child_metadatas).
    """
    child_ids = []
    child_texts = []
    child_metadatas = []

    parent_chunks = parent_splitter.split_text(text)
    if not parent_chunks:
        parent_chunks = [text[:2000]]

    for p_idx, parent_text in enumerate(parent_chunks):
        parent_id = f"{source_id}_P{p_idx+1}"
        c_chunks = child_splitter.split_text(parent_text)
        if not c_chunks:
            c_chunks = [parent_text[:300]]

        for c_idx, child_text in enumerate(c_chunks):
            child_id = f"{parent_id}_C{c_idx+1}"
            child_ids.append(child_id)
            child_texts.append(child_text)
            child_metadatas.append({
                "source_id": source_id,
                "parent_id": parent_id,
                "parent_text": parent_text,
                "source_type": source_type,
                "title": title[:200]
            })

    return child_ids, child_texts, child_metadatas


def add_documents(documents: List[Dict[str, Any]]) -> int:
    """
    Generates Parent-Child chunks, embeds child chunks, and upserts to ChromaDB.
    """
    if not documents:
        return 0

    collection = get_collection()
    model = get_embed_model()

    all_child_ids = []
    all_child_texts = []
    all_child_metadatas = []

    for doc in documents:
        source_id = str(doc.get("source_id") or doc.get("patent_id") or doc.get("id") or "").strip()
        text = str(doc.get("text") or doc.get("abstract") or "").strip()
        source_type = str(doc.get("source_type") or "patent")
        title = str(doc.get("title") or "")

        if not source_id or not text:
            continue

        c_ids, c_texts, c_metas = create_parent_child_chunks(
            source_id=source_id,
            text=text,
            source_type=source_type,
            title=title
        )
        all_child_ids.extend(c_ids)
        all_child_texts.extend(c_texts)
        all_child_metadatas.extend(c_metas)

    if not all_child_texts:
        return 0

    embeddings = model.encode(all_child_texts, show_progress_bar=False).tolist()

    collection.upsert(
        ids=all_child_ids,
        embeddings=embeddings,
        documents=all_child_texts,
        metadatas=all_child_metadatas
    )

    logger.info(f"Parent-Child Indexing: Upserted {len(all_child_ids)} child chunks across documents into '{COLLECTION_NAME}'")
    return len(all_child_ids)


def query_similar(query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Queries ChromaDB child chunk embeddings with user_query.
    Deduplicates and retrieves full Parent Chunk text snippets for the top matches.
    """
    if not query_text or not query_text.strip():
        return []

    collection = get_collection()
    if collection.count() == 0:
        return []

    model = get_embed_model()
    query_embedding = model.encode([query_text], show_progress_bar=False).tolist()

    # Query extra child matches to allow for parent-level deduplication
    fetch_count = min(top_k * 4, collection.count())
    results = collection.query(
        query_embeddings=query_embedding,
        n_results=fetch_count,
        include=["documents", "metadatas", "distances"]
    )

    seen_parents = set()
    formatted_results = []

    if results and "ids" in results and results["ids"]:
        ids_list = results["ids"][0]
        docs_list = results.get("documents", [[]])[0]
        meta_list = results.get("metadatas", [[]])[0]
        dist_list = results.get("distances", [[]])[0]

        for i in range(len(ids_list)):
            meta = meta_list[i] if i < len(meta_list) else {}
            parent_id = meta.get("parent_id") or ids_list[i]
            source_id = meta.get("source_id") or parent_id

            if parent_id in seen_parents:
                continue

            seen_parents.add(parent_id)

            dist = float(dist_list[i]) if i < len(dist_list) else 1.0
            similarity = max(0.0, min(1.0, 1.0 - (dist / 2.0) if dist > 1.0 else 1.0 - dist))
            parent_text = meta.get("parent_text") or (docs_list[i] if i < len(docs_list) else "")

            formatted_results.append({
                "source_id": source_id,
                "parent_id": parent_id,
                "text_snippet": parent_text[:2000],  # Full parent chunk context
                "distance": round(dist, 4),
                "similarity": round(similarity, 4),
                "title": meta.get("title", ""),
                "source_type": meta.get("source_type", "patent")
            })

            if len(formatted_results) >= top_k:
                break

    return formatted_results
