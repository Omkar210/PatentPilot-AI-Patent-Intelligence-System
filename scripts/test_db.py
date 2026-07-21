"""
scripts/test_db.py — Database End-to-End Smoke Test

Inserts a dummy Patent record using db.session and reads it back to confirm
models -> migration -> session -> PostgreSQL connection works end-to-end.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from db.models import Patent
from db.session import SessionLocal

console = Console()


def test_db_chain():
    console.print("[bold blue]Starting DB End-to-End Test...[/bold blue]")
    db = SessionLocal()
    try:
        # Create a dummy patent record
        dummy_id = "US-TEST-123456"
        dummy_patent = Patent(
            patent_id=dummy_id,
            title="AI-Powered Patent Intelligence System and Method",
            abstract="A multi-agent AI system for searching, analyzing, and assessing novelty of patents.",
            inventors=["Omkar Team", "CDAC Research Group"],
            ipc_codes=["G06N 20/00", "G06F 16/90"],
            pdf_url="https://example.com/patent.pdf",
            raw_text="Sample raw patent text for testing purposes."
        )

        # Cleanup existing dummy test record if any
        existing = db.query(Patent).filter(Patent.patent_id == dummy_id).first()
        if existing:
            db.delete(existing)
            db.commit()

        # Insert dummy record
        db.add(dummy_patent)
        db.commit()
        console.print(f"[green]✓ Inserted dummy patent record (patent_id={dummy_id})[/green]")

        # Read back from database
        fetched = db.query(Patent).filter(Patent.patent_id == dummy_id).first()
        assert fetched is not None, "Failed to retrieve inserted patent record!"
        assert fetched.title == dummy_patent.title, "Fetched title mismatch!"
        assert fetched.inventors == ["Omkar Team", "CDAC Research Group"], "Fetched inventors mismatch!"

        console.print("[bold green]✓ DB Readback Successful:[/bold green]")
        console.print(f"  ID: {fetched.id}")
        console.print(f"  Patent ID: {fetched.patent_id}")
        console.print(f"  Title: {fetched.title}")
        console.print(f"  Inventors: {fetched.inventors}")
        console.print(f"  IPC Codes: {fetched.ipc_codes}")
        console.print(f"  Created At: {fetched.created_at}")

        # Cleanup after test
        db.delete(fetched)
        db.commit()
        console.print("[green]✓ Cleaned up test record[/green]")

        console.print("\n[bold green]>>> DB End-to-End Test PASSED <<<[/bold green]")
        return True
    except Exception as e:
        console.print(f"[bold red]✗ DB Test Failed: {e}[/bold red]")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_db_chain()
    sys.exit(0 if success else 1)
