import os
import uuid
import time
import logging
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, Depends, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from patentmind.db.session import get_db, init_db
from patentmind.db.models import Patent, EmbeddingsMeta, ProcessingLog
from patentmind.retrieval.rag_pipeline import get_rag_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PatentMindAPI")

app = FastAPI(
    title="PatentMind AI - Enterprise Patent Intelligence Platform",
    description="Big Data + RAG + LLM System for Patent Retrieval & Intelligence",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    logger.info("PatentMind API initialized successfully.")

# Schemas
class QueryRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None

class SourceItem(BaseModel):
    patent_number: str
    section: str
    score: float
    chunk_text: str

class QueryResponse(BaseModel):
    query_id: str
    query: str
    answer: str
    sources: List[SourceItem]
    llm_backend_used: str
    vector_backend_used: str

@app.post("/api/query", response_model=QueryResponse)
def run_query(req: QueryRequest):
    start_time = time.time()
    query_id = str(uuid.uuid4())[:8]
    pipeline = get_rag_pipeline()
    
    result = pipeline.process_query(query=req.query)
    elapsed = round(time.time() - start_time, 2)
    logger.info(f"Query [{query_id}] completed in {elapsed}s via {result['llm_backend_used']}")

    return QueryResponse(
        query_id=query_id,
        query=req.query,
        answer=result["answer"],
        sources=result["sources"],
        llm_backend_used=result["llm_backend_used"],
        vector_backend_used=result["vector_backend_used"]
    )

@app.post("/api/query-with-paper", response_model=QueryResponse)
async def run_query_with_paper(
    query: str = Form(...),
    paper: UploadFile = File(...)
):
    start_time = time.time()
    query_id = str(uuid.uuid4())[:8]
    paper_bytes = await paper.read()
    
    pipeline = get_rag_pipeline()
    result = pipeline.process_query(query=query, paper_bytes=paper_bytes)
    elapsed = round(time.time() - start_time, 2)
    logger.info(f"Query-with-paper [{query_id}] completed in {elapsed}s")

    return QueryResponse(
        query_id=query_id,
        query=query,
        answer=result["answer"],
        sources=result["sources"],
        llm_backend_used=result["llm_backend_used"],
        vector_backend_used=result["vector_backend_used"]
    )

@app.get("/api/patents")
def get_patents(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    source: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Patent)
    if source:
        query = query.filter(Patent.source_repository.ilike(f"%{source}%"))
    
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    
    results = []
    for p in items:
        results.append({
            "patent_id": p.patent_id,
            "patent_number": p.patent_number,
            "title": p.title,
            "abstract": p.abstract,
            "assignee": p.assignee,
            "source_repository": p.source_repository,
            "publication_date": p.publication_date,
            "processing_status": p.processing_status
        })

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "items": results
    }

@app.get("/api/patents/{patent_number}")
def get_patent_detail(patent_number: str, db: Session = Depends(get_db)):
    patent = db.query(Patent).filter(Patent.patent_number == patent_number).first()
    if not patent:
        raise HTTPException(status_code=404, detail=f"Patent {patent_number} not found.")
    
    return {
        "patent_id": patent.patent_id,
        "patent_number": patent.patent_number,
        "title": patent.title,
        "abstract": patent.abstract,
        "claims": patent.claims,
        "description": patent.description,
        "inventors": patent.inventors,
        "assignee": patent.assignee,
        "filing_date": patent.filing_date,
        "publication_date": patent.publication_date,
        "cpc_codes": patent.cpc_codes,
        "ipc_codes": patent.ipc_codes,
        "pdf_url": patent.pdf_url,
        "s3_key": patent.s3_key,
        "source_repository": patent.source_repository,
        "domain_tags": patent.domain_tags,
        "processing_status": patent.processing_status
    }

@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    total_patents = db.query(Patent).count()
    sources = db.query(Patent.source_repository, func.count(Patent.patent_id)).group_by(Patent.source_repository).all()
    statuses = db.query(Patent.processing_status, func.count(Patent.patent_id)).group_by(Patent.processing_status).all()

    pipeline = get_rag_pipeline()

    # Try to fetch Neo4j graph stats
    graph_stats = {"patents": 0, "inventors": 0, "assignees": 0, "cpc_codes": 0}
    try:
        from patentmind.graph.neo4j_client import get_neo4j_client
        neo4j = get_neo4j_client()
        graph_stats = neo4j.get_graph_stats()
    except Exception:
        pass

    return {
        "total_patents": total_patents,
        "source_breakdown": {s: cnt for s, cnt in sources if s},
        "status_breakdown": {st: cnt for st, cnt in statuses if st},
        "vector_backend": pipeline.vector_store.backend.upper(),
        "gpu_server": "192.168.6.50:22 (Qwen3-4B / GLM-OCR)",
        "graph_stats": graph_stats
    }

@app.get("/api/graph/patent/{patent_number}")
def get_patent_graph(patent_number: str):
    """Return Neo4j graph neighbourhood for a patent."""
    try:
        from patentmind.graph.neo4j_client import get_neo4j_client
        neo4j = get_neo4j_client()
        return neo4j.get_patent_network(patent_number)
    except Exception as e:
        return {"patent_number": patent_number, "error": str(e), "inventors": [], "assignees": [], "cpc_codes": []}

@app.post("/api/compare-pdf")
async def compare_pdf(paper: UploadFile = File(...)):
    """
    Dedicated PDF comparison endpoint.
    1. Extracts text from uploaded PDF (PyMuPDF)
    2. Cleans text
    3. Encodes text and searches Qdrant for top-k semantically similar patents
    4. For top matching patent numbers, fetches Neo4j knowledge graph data
    5. Generates LLM novelty assessment combining semantic + graph evidence
    Returns: {semantic_matches, graph_data, synthesis, llm_backend_used, vector_backend_used}
    """
    start_time = time.time()
    paper_bytes = await paper.read()
    
    # 1. Extract and clean PDF text
    from patentmind.processing.pdf_extractor import PDFExtractor
    from patentmind.processing.cleaner import PatentTextCleaner
    pages = PDFExtractor.extract_pages(paper_bytes)
    raw_text = "\n".join([p["text"] for p in pages])
    cleaned_text = PatentTextCleaner.clean_text(raw_text)
    
    # 2. Semantic search via Qdrant
    pipeline = get_rag_pipeline()
    query_embedding = pipeline.encoder.batch_encode([cleaned_text[:2000]])[0]
    hits = pipeline.vector_store.search(query_embedding, top_k=8)
    
    semantic_matches = []
    seen_patents = set()
    for hit in hits:
        pn = hit["patent_number"]
        score = hit["score"]
        semantic_matches.append({
            "patent_number": pn,
            "section": hit["section_name"],
            "score": score,
            "chunk_text": hit["chunk_text"]
        })
        seen_patents.add(pn)
    
    # 3. Knowledge graph data for top matching patents
    graph_data = {"shared_inventors": [], "shared_cpc": [], "assignee_portfolio": []}
    try:
        from patentmind.graph.neo4j_client import get_neo4j_client
        neo4j = get_neo4j_client()
        for pn in list(seen_patents)[:5]:
            network = neo4j.get_patent_network(pn)
            if network.get("inventors"):
                graph_data["shared_inventors"].extend(
                    [{"inventor": inv, "patent": pn, "title": network.get("title", "")} for inv in network["inventors"]]
                )
            if network.get("cpc_codes"):
                for cpc in network["cpc_codes"]:
                    related = neo4j.find_patents_by_cpc(cpc)
                    graph_data["shared_cpc"].append({"code": cpc, "patent_count": len(related), "patents": related[:5]})
            if network.get("assignees"):
                for asg in network["assignees"]:
                    graph_data["assignee_portfolio"].append({"assignee": asg, "patent": pn})
    except Exception as e:
        logger.warning(f"Graph data fetch error: {e}")
    
    # Deduplicate
    seen_inv = set()
    unique_inventors = []
    for item in graph_data["shared_inventors"]:
        key = (item["inventor"], item["patent"])
        if key not in seen_inv:
            seen_inv.add(key)
            unique_inventors.append(item)
    graph_data["shared_inventors"] = unique_inventors
    
    seen_cpc = set()
    unique_cpc = []
    for item in graph_data["shared_cpc"]:
        if item["code"] not in seen_cpc:
            seen_cpc.add(item["code"])
            unique_cpc.append(item)
    graph_data["shared_cpc"] = unique_cpc
    
    # 4. LLM Novelty Synthesis
    synthesis_prompt = (
        "You are a Patent Novelty Analyst. Given the following uploaded patent text and semantically similar existing patents, "
        "provide a novelty assessment. Score novelty from 0 to 100. Identify the key novel elements not found in existing patents. "
        "Cite specific patent numbers as evidence. Be concise but thorough.\n\n"
        f"=== UPLOADED PATENT TEXT (excerpt) ===\n{cleaned_text[:3000]}\n\n"
        f"=== TOP SEMANTIC MATCHES ===\n"
    )
    for m in semantic_matches[:5]:
        synthesis_prompt += f"Patent {m['patent_number']} ({m['section']}, {m['score']:.0%} match): {m['chunk_text'][:200]}\n\n"
    synthesis_prompt += "Provide your novelty assessment:"
    
    llm_response = pipeline.router.generate(synthesis_prompt)
    
    elapsed = round(time.time() - start_time, 2)
    logger.info(f"PDF comparison completed in {elapsed}s")
    
    return {
        "semantic_matches": semantic_matches,
        "graph_data": graph_data,
        "synthesis": {
            "assessment": llm_response["answer"],
            "llm_backend_used": llm_response["llm_backend_used"],
            "elapsed_seconds": elapsed
        },
        "vector_backend_used": pipeline.vector_store.backend.upper(),
        "total_elapsed": elapsed
    }

@app.get("/api/system-status")
def get_system_status():
    """Return live connectivity status for Qdrant, Ollama, Neo4j, and Groq."""
    status = {}
    
    # Qdrant
    try:
        pipeline = get_rag_pipeline()
        collections = pipeline.vector_store.qdrant_client.get_collections()
        status["qdrant"] = {"status": "active", "collections": len(collections.collections)}
    except Exception:
        status["qdrant"] = {"status": "offline"}
    
    # Ollama
    try:
        import httpx
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                models = r.json().get("models", [])
                status["ollama"] = {"status": "active", "models": [m["name"] for m in models]}
            else:
                status["ollama"] = {"status": "offline"}
    except Exception:
        status["ollama"] = {"status": "offline"}
    
    # Neo4j
    try:
        from patentmind.graph.neo4j_client import get_neo4j_client
        neo4j = get_neo4j_client()
        if neo4j.driver:
            neo4j.driver.verify_connectivity()
            status["neo4j"] = {"status": "active"}
        else:
            status["neo4j"] = {"status": "offline"}
    except Exception:
        status["neo4j"] = {"status": "offline"}
    
    # Groq
    groq_key = os.getenv("GROQ_API_KEY", "")
    status["groq"] = {"status": "standby" if groq_key else "no_key"}
    
    return status

# Mount static files if frontend build exists
frontend_dist = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
