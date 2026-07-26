#!/usr/bin/env python3
"""
PatentMind AI - Master Service Launcher & Orchestrator
=====================================================

This single script checks, initializes, and launches all microservices and background 
components required to run the full PatentMind AI system:

1. Environment Configuration (.env loading)
2. Relational Database Initialization (PostgreSQL / SQLite fallback)
3. Qdrant Vector Engine Connectivity & Collection Setup
4. Ollama LLM Service Check / Subprocess Launch (Qwen3-4B / Qwen2.5:3b)
5. Neo4j Graph Database Connectivity Verification
6. FastAPI Web Server & UI Static Host (Uvicorn on port 8000)

Usage:
    python start_all_services.py [--worker] [--host HOST] [--port PORT]

Options:
    --worker  : Optionally run the batch S3 GPU worker before launching web server
    --host    : Server host (default: 0.0.0.0)
    --port    : Server port (default: 8000)
"""

import os
import sys
import subprocess
import socket
import time
import argparse

# ── Auto Virtual Environment Check & Activation ─────────────────────
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)

def ensure_venv():
    """Ensure script runs inside project virtual environment (.venv)."""
    venv_dir = os.path.join(ROOT_DIR, ".venv")
    if sys.platform == "win32":
        venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        alt_venv_python = os.path.join(ROOT_DIR, "patentmind", ".venv", "Scripts", "python.exe")
    else:
        venv_python = os.path.join(venv_dir, "bin", "python")
        alt_venv_python = os.path.join(ROOT_DIR, "patentmind", ".venv", "bin", "python")

    # Pick existing venv executable if found
    target_python = None
    if os.path.exists(venv_python):
        target_python = venv_python
    elif os.path.exists(alt_venv_python):
        target_python = alt_venv_python

    # Check if current running python matches target venv python
    in_venv = hasattr(sys, "real_prefix") or (getattr(sys, "base_prefix", sys.prefix) != sys.prefix)
    
    script_path = os.path.abspath(sys.argv[0])
    
    if target_python and os.path.abspath(sys.executable).lower() != os.path.abspath(target_python).lower():
        print(f"[Virtual Environment] Switching to project .venv ({target_python})...")
        sys.exit(subprocess.call([target_python, script_path] + sys.argv[1:]))
    elif not in_venv and not target_python:
        print("[Virtual Environment] Creating new .venv with Python 3.11...")
        try:
            subprocess.run(["py", "-3.11", "-m", "venv", venv_dir], check=True)
        except Exception:
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)
        
        target_python = venv_python if os.path.exists(venv_python) else sys.executable
        print("[Virtual Environment] Installing requirements into .venv...")
        req_file = os.path.join(ROOT_DIR, "patentmind", "requirements.txt")
        if os.path.exists(req_file):
            subprocess.run([target_python, "-m", "pip", "install", "-r", req_file], check=True)
        
        print("[Virtual Environment] Re-launching inside .venv...")
        sys.exit(subprocess.call([target_python, script_path] + sys.argv[1:]))

ensure_venv()

# ── Import Third-Party Libraries ─────────────────────────────────────
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT_DIR, "patentmind", ".env"))
load_dotenv(os.path.join(ROOT_DIR, ".env"))

console = Console()

def check_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Check if a TCP port is open and listening."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def print_banner():
    console.print(Panel.fit(
        "[bold orange1]PatentMind AI — Master Service Orchestrator[/bold orange1]\n"
        "[dim]Big Data + RAG + Knowledge Graph + Dual LLM Fallback Engine[/dim]",
        border_style="orange1"
    ))

def check_and_init_db():
    console.print("\n[bold cyan]1. Database Layer Check[/bold cyan]")
    db_url = os.getenv("DATABASE_URL", "sqlite:///./patentmind_fallback.db")
    console.print(f"   DATABASE_URL: [yellow]{db_url}[/yellow]")
    
    try:
        from patentmind.db.session import init_db
        init_db()
        console.print("   [bold green]✓ Relational database initialized successfully (tables created/verified).[/bold green]")
    except Exception as e:
        console.print(f"   [bold red]✕ Database initialization error: {e}[/bold red]")

def check_qdrant():
    console.print("\n[bold cyan]2. Qdrant Vector Engine Check[/bold cyan]")
    qdrant_host = os.getenv("QDRANT_HOST", "127.0.0.1")
    qdrant_port = int(os.getenv("QDRANT_PORT", "6333"))
    
    try:
        from patentmind.embeddings.vector_store import get_vector_store
        vs = get_vector_store()
        console.print(f"   [bold green]✓ Vector Store ready (Backend: {vs.backend.upper()})[/bold green]")
    except Exception as e:
        console.print(f"   [bold red]✕ Vector Store error: {e}[/bold red]")

def check_ollama():
    console.print("\n[bold cyan]3. Ollama LLM Engine Check[/bold cyan]")
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    console.print(f"   OLLAMA_BASE_URL: [yellow]{ollama_url}[/yellow]")
    
    is_running = False
    try:
        with httpx.Client(timeout=3.0) as client:
            r = client.get(f"{ollama_url}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                console.print(f"   [bold green]✓ Ollama active. Installed models: {models}[/bold green]")
                is_running = True
    except Exception:
        pass

    if not is_running:
        console.print(f"   [bold yellow]⚠ Ollama service not responding at {ollama_url}.[/bold yellow]")
        console.print("   Automatic Fallback: LLMRouter will direct queries to [bold green]Groq API (llama-3.3-70b)[/bold green] when Ollama is unavailable.")
        
        # Try to launch local ollama serve if command exists
        if "127.0.0.1" in ollama_url or "localhost" in ollama_url:
            console.print("   Attempting background launch of local 'ollama serve'...")
            try:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
                console.print("   [green]Launched 'ollama serve' process in background.[/green]")
            except FileNotFoundError:
                console.print("   [dim]'ollama' CLI binary not found in PATH — operating in Groq fallback mode.[/dim]")

def check_neo4j():
    console.print("\n[bold cyan]4. Neo4j Knowledge Graph Check[/bold cyan]")
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")

    # Extract host/port from URI for a fast TCP check before attempting driver connection
    try:
        uri_body = neo4j_uri.replace("bolt://", "").replace("neo4j://", "")
        neo4j_host, neo4j_port = uri_body.split(":")
        neo4j_port = int(neo4j_port)
    except Exception:
        neo4j_host, neo4j_port = "localhost", 7687

    if not check_port(neo4j_host, neo4j_port, timeout=1.5):
        console.print(f"   [dim]⚠ Neo4j offline ({neo4j_host}:{neo4j_port}) — graph features using simulated fallback.[/dim]")
        return

    # Port is open — attempt full driver connection
    try:
        from patentmind.graph.neo4j_client import get_neo4j_client
        neo4j = get_neo4j_client()
        if neo4j.driver:
            stats = neo4j.get_graph_stats()
            console.print(f"   [bold green]✓ Neo4j active at {neo4j_uri}. Graph stats: {stats}[/bold green]")
        else:
            console.print("   [bold yellow]⚠ Neo4j driver offline. Graph features will return simulated responses.[/bold yellow]")
    except Exception:
        console.print("   [bold yellow]⚠ Neo4j driver offline. Graph features will return simulated responses.[/bold yellow]")

def run_optional_worker():
    console.print("\n[bold cyan]5. S3 Ingestion Worker — Checking for new patents...[/bold cyan]")
    try:
        # Fast check: if Qdrant already has vectors, only run worker if there are genuinely new S3 PDFs
        from patentmind.embeddings.vector_store import get_vector_store
        vs = get_vector_store()
        existing_count = vs.get_vector_count()

        if existing_count > 0:
            # Peek at S3 to see if there are any unindexed PDFs without loading full worker
            import boto3
            bucket_name = os.getenv("S3_BUCKET_NAME")
            if not bucket_name:
                console.print("   [dim]S3_BUCKET_NAME not set — skipping worker.[/dim]")
                return

            s3 = boto3.client('s3',
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                region_name=os.getenv('AWS_REGION')
            )
            response = s3.list_objects_v2(Bucket=bucket_name)
            pdf_keys = [obj['Key'] for obj in response.get('Contents', []) if obj['Key'].lower().endswith('.pdf')]
            s3_patent_numbers = {os.path.basename(k).replace('.pdf','').replace('.PDF','') for k in pdf_keys}

            existing_patents = vs.get_existing_patent_numbers()
            new_patents = s3_patent_numbers - existing_patents

            if not new_patents:
                console.print(f"   [bold green]✓ All {len(s3_patent_numbers)} S3 patents already indexed ({existing_count} vectors). No ingestion needed.[/bold green]")
                return
            else:
                console.print(f"   [cyan]Found {len(new_patents)} new unindexed patents — running ingestion worker...[/cyan]")

        from gpu_worker import run_gpu_worker
        run_gpu_worker()
    except Exception as e:
        console.print(f"   [bold red]✕ Worker error: {e}[/bold red]")

def print_summary_table(host: str, port: int):
    table = Table(title="PatentMind AI System Service Summary", show_header=True, header_style="bold orange1")
    table.add_column("Component", style="cyan")
    table.add_column("Endpoint / Config", style="yellow")
    table.add_column("Role & Description", style="dim")
    
    table.add_row("FastAPI Web Server", f"http://{host}:{port}", "REST APIs & Web UI Host")
    table.add_row("Frontend UI", f"http://{host}:{port}/", "Single-Page Application (Terracotta Theme)")
    table.add_row("Relational Database", os.getenv("DATABASE_URL", "sqlite:///./patentmind_fallback.db")[:35], "Metadata & Audit Logs")
    table.add_row("Qdrant Vector DB", f"{os.getenv('QDRANT_HOST', '127.0.0.1')}:{os.getenv('QDRANT_PORT', '6333')}", "Vector Embeddings Storage")
    table.add_row("Ollama LLM", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"), "Primary Local LLM (Qwen3-4B)")
    table.add_row("Groq Cloud API", "Groq llama-3.3-70b", "Secondary Automatic LLM Fallback")
    table.add_row("Neo4j Knowledge Graph", os.getenv("NEO4J_URI", "bolt://localhost:7687"), "Patent Network & Entity Traversal")
    
    console.print("\n")
    console.print(table)

def launch_fastapi_server(host: str, port: int):
    console.print(f"\n[bold green]🚀 Launching FastAPI Web Server on http://{host}:{port}...[/bold green]\n")
    import uvicorn
    uvicorn.run("patentmind.api.main:app", host=host, port=port, reload=False, log_level="info")

def main():
    parser = argparse.ArgumentParser(description="PatentMind AI - Service Launcher")
    parser.add_argument("--worker", action="store_true", help="Run batch S3 GPU worker before starting API")
    parser.add_argument("--host", default="0.0.0.0", help="Host address for FastAPI server")
    parser.add_argument("--port", type=int, default=8000, help="Port for FastAPI server")
    args = parser.parse_args()

    print_banner()
    check_and_init_db()
    check_qdrant()
    check_ollama()
    check_neo4j()
    
    if args.worker:
        run_optional_worker()

    print_summary_table(args.host, args.port)
    launch_fastapi_server(args.host, args.port)

if __name__ == "__main__":
    main()
