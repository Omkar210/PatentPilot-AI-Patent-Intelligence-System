import asyncio
import os
import aiohttp
from typing import Dict, List, Any
from rich.console import Console
from rich.table import Table
from patentmind.ingestion.uspto_client import USPTOClient
from patentmind.ingestion.wipo_client import WIPOClient
from patentmind.ingestion.google_patents_client import GooglePatentsClient
from patentmind.ingestion.openalex_client import OpenAlexClient
from patentmind.ingestion.arxiv_client import ArxivClient
from patentmind.storage.s3_client import s3_client
from patentmind.db.session import SessionLocal, init_db
from patentmind.db.models import Patent, ProcessingLog

console = Console()

DOMAINS = [
    "Artificial Intelligence",
    "RAG Systems",
    "Large Language Models",
    "AI Agents",
    "Image Generation",
    "Speech Recognition",
    "Recommendation Systems",
    "Machine learning",
    "Deep Learning",
    "Computer Vision",
    "Generative AI",
    "Agentic AI"
]

async def download_pdf_with_semaphore(url: str, semaphore: asyncio.Semaphore) -> bytes:
    async with semaphore:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        return await response.read()
        except Exception as e:
            console.print(f"[dim]Network error downloading {url}: {e}[/dim]")
        return b""

async def process_single_patent(p: Dict[str, Any], semaphore: asyncio.Semaphore, session) -> bool:
    try:
        # 1. Check SQLite DB directly to prevent duplicate downloads
        existing_patent = session.query(Patent).filter(Patent.patent_number == p["patent_number"]).first()
        if existing_patent:
            return False
            
        # 2. Check physical AWS S3 bucket directly to prevent duplicate downloads
        expected_s3_key = f"dataset/{p['patent_number']}.pdf"
        s3_path = expected_s3_key
        pdf_bytes = None
        already_in_s3 = s3_client.check_exists(expected_s3_key)
        
        if not already_in_s3:
            # 3. Download physical PDF with concurrency limit
            if not p.get("pdf_url"):
                return False
                
            console.print(f"Downloading physical PDF for {p['patent_number']} from \n{p['pdf_url']}...")
            pdf_bytes = await download_pdf_with_semaphore(p["pdf_url"], semaphore)
            
            if not pdf_bytes or len(pdf_bytes) < 1000:
                console.print(f"[red]Failed to download valid PDF for {p['patent_number']}[/red]")
                return False
                
            # 4. Upload to S3
            s3_path = s3_client.upload_patent_pdf(p["patent_number"], pdf_bytes)
            if not s3_path:
                return False
        else:
            console.print(f"[dim]Skipping download for {p['patent_number']}, PDF already exists in S3[/dim]")

        # 5. Insert metadata into SQLite
        db_patent = Patent(
            patent_number=p["patent_number"],
            title=p.get("title", ""),
            abstract=p.get("abstract", ""),
            claims=p.get("claims", ""),
            description=p.get("description", ""),
            inventors=p.get("inventors", []),
            assignee=p.get("assignee", ""),
            filing_date=p.get("filing_date"),
            publication_date=p.get("publication_date"),
            cpc_codes=p.get("cpc_codes", []),
            ipc_codes=p.get("ipc_codes", []),
            pdf_url=p.get("pdf_url", ""),
            s3_key=s3_path,
            source_repository=p.get("source_repository", "Unknown"),
            domain_tags=p.get("domain_tags", [])
        )
        session.add(db_patent)
        session.flush() # To get the patent_id
        
        db_log = ProcessingLog(
            patent_id=db_patent.patent_id,
            stage="ingestion",
            status="COMPLETED",
            error_message=""
        )
        session.add(db_log)
        session.commit()
        
        return True
    except Exception as e:
        session.rollback()
        console.print(f"[red]Error saving patent {p['patent_number']} to DB: {e}[/red]")
        return False

async def run_ingestion_pipeline() -> Dict[str, Any]:
    console.print("[bold cyan]Starting MASSIVE Patent Ingestion Pipeline...[/bold cyan]")
    
    init_db()

    openalex = OpenAlexClient()
    arxiv_client = ArxivClient()

    seen_numbers = set()
    total_stored = 0
    total_raw = 0
    
    download_semaphore = asyncio.Semaphore(5) # Max 5 concurrent downloads to save RAM/Network
    
    db_session = SessionLocal()

    try:
        for domain in DOMAINS:
            console.print(f"\n[bold magenta]=== Processing Domain: {domain} ===[/bold magenta]")
            
            # Fetch 1000 from OpenAlex and 1000 from ArXiv per domain
            openalex_task = openalex.fetch_ai_patents(1000, domain_keyword=domain)
            arxiv_task = arxiv_client.fetch_ai_patents(1000, domain_keyword=domain)
            
            openalex_res, arxiv_res = await asyncio.gather(openalex_task, arxiv_task)
            
            all_raw_domain = openalex_res + arxiv_res
            total_raw += len(all_raw_domain)
            console.print(f"Fetched {len(all_raw_domain)} raw documents for '{domain}'.")

            unique_domain_patents = []
            for p in all_raw_domain:
                if p["patent_number"] not in seen_numbers:
                    unique_domain_patents.append(p)
                    seen_numbers.add(p["patent_number"])

            console.print(f"Found {len(unique_domain_patents)} unique new documents for '{domain}'. Downloading PDFs...")
            
            # Run downloads for this domain concurrently, but bounded by the semaphore
            tasks = [process_single_patent(p, download_semaphore, db_session) for p in unique_domain_patents]
            results = await asyncio.gather(*tasks)
            
            successes = sum(1 for r in results if r)
            total_stored += successes
            console.print(f"[bold green]Successfully downloaded & stored {successes} PDFs for '{domain}'.[/bold green]")
            
            # Give APIs a breather between domains
            await asyncio.sleep(5.0)

    finally:
        db_session.close()

    console.print("\n[bold cyan]  Mass Ingestion Pipeline Summary  [/bold cyan]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Metric / Source", style="dim", width=30)
    table.add_column("Count", justify="right")
    
    table.add_row("Total Raw Fetched across Domains", str(total_raw))
    table.add_row("Total Processed Unique", str(len(seen_numbers)))
    table.add_row("Final Stored in DB & S3", str(total_stored))
    
    console.print(table)
    
    return {
        "raw_fetched": total_raw,
        "processed": len(seen_numbers),
        "stored": total_stored
    }

if __name__ == "__main__":
    asyncio.run(run_ingestion_pipeline())
