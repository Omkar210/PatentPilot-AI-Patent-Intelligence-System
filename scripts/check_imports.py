"""
scripts/check_imports.py — PatentPilot AI import smoke-test

Run after installing requirements.txt to confirm all packages
import cleanly and version pins are satisfied.

Usage:
    python -X utf8 scripts/check_imports.py
"""

import os
import sys
import importlib

# Force UTF-8 output on Windows so Rich can render without cp1252 errors
os.environ.setdefault("PYTHONUTF8", "1")
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table

console = Console(highlight=False)

CHECKS = [
    # (import_path, display_name, version_attr)
    # Backend
    ("fastapi",                 "FastAPI",               "__version__"),
    ("uvicorn",                 "Uvicorn",               "__version__"),
    # Database
    ("sqlalchemy",              "SQLAlchemy",            "__version__"),
    ("psycopg2",                "psycopg2",              "__version__"),
    ("alembic",                 "Alembic",               "__version__"),
    # Environment
    ("dotenv",                  "python-dotenv",         None),
    ("multipart",               "python-multipart",      None),
    # LangChain / LangGraph
    ("langgraph",               "LangGraph",             "__version__"),
    ("langchain",               "LangChain",             "__version__"),
    ("langchain_community",     "LangChain Community",   "__version__"),
    ("langchain_core",          "LangChain Core",        "__version__"),
    # Vector DB
    ("chromadb",                "ChromaDB",              "__version__"),
    # Graph DB
    ("neo4j",                   "Neo4j Driver",          "__version__"),
    ("networkx",                "NetworkX",              "__version__"),
    # Embeddings
    ("sentence_transformers",   "Sentence Transformers", "__version__"),
    # Data Processing
    ("pandas",                  "Pandas",                "__version__"),
    ("numpy",                   "NumPy",                 "__version__"),
    # HTTP
    ("httpx",                   "HTTPX",                 "__version__"),
    ("requests",                "Requests",              "__version__"),
    # PDF
    ("fitz",                    "PyMuPDF (fitz)",        "__version__"),
    # OCR (optional — no Py3.14 wheel; skip gracefully)
    ("paddleocr",               "PaddleOCR [optional]",  None),
    # Computer Vision
    ("cv2",                     "OpenCV",                "__version__"),
    ("PIL",                     "Pillow",                "__version__"),
    # LLM local (optional)
    ("transformers",            "Transformers",          "__version__"),
    ("accelerate",              "Accelerate",            "__version__"),
    # Hosted LLM
    ("groq",                    "Groq SDK",              "__version__"),
    ("google.generativeai",     "Google GenerativeAI",   "__version__"),
    # Utilities
    ("tqdm",                    "tqdm",                  "__version__"),
    ("rich",                    "Rich",                  "__version__"),
]

OPTIONAL = {"PaddleOCR [optional]"}


def check_imports() -> bool:
    table = Table(title="PatentPilot AI -- Package Import Check", show_lines=True)
    table.add_column("Package", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Version", style="dim")

    all_ok = True
    for import_path, display_name, version_attr in CHECKS:
        try:
            mod = importlib.import_module(import_path)
            version = getattr(mod, version_attr) if version_attr and hasattr(mod, version_attr) else "-"
            table.add_row(display_name, "[green] OK [/green]", str(version))
        except ImportError as e:
            optional = display_name in OPTIONAL
            status = "[yellow]SKIP[/yellow]" if optional else "[red]FAIL[/red]"
            table.add_row(display_name, status, str(e)[:60])
            if not optional:
                all_ok = False
        except Exception as e:
            table.add_row(display_name, "[yellow]WARN[/yellow]", str(e)[:60])

    console.print(table)

    # Verify state.py loads cleanly
    console.print("\n[bold]Checking state.py...[/bold]")
    try:
        sys.path.insert(0, ".")
        from state import PatentPilotState
        fields = list(PatentPilotState.__annotations__.keys())
        console.print(f"[green] OK [/green] PatentPilotState — {len(fields)} fields")
        console.print(f"       {fields}")
    except Exception as e:
        console.print(f"[red]FAIL[/red] state.py: {e}")
        all_ok = False

    console.print()
    if all_ok:
        console.print("[bold green]>>> All checks passed <<<[/bold green]")
    else:
        console.print("[bold red]>>> Some checks FAILED — review output above <<<[/bold red]")

    return all_ok


if __name__ == "__main__":
    ok = check_imports()
    sys.exit(0 if ok else 1)
