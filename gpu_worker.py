import os
import sys
import boto3
import threading
import multiprocessing as mp
from typing import List, Tuple, Optional
from rich.console import Console
from rich.progress import (
    Progress, SpinnerColumn, TextColumn, BarColumn, 
    TaskProgressColumn, MofNCompleteColumn, TimeRemainingColumn
)
from dotenv import load_dotenv

try:
    import torch
except Exception as e:
    torch = None
    print(f"[Warning] PyTorch import error ({e}). Pipeline will run with CPU/HashEncoder.")

# Ensure the root directory is in sys.path so 'patentmind' module can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from patentmind.embeddings.encoder import EmbeddingEncoder
from patentmind.storage.s3_client import s3_client
from patentmind.processing.ocr_engine import get_glm_ocr_engine
from patentmind.processing.pdf_extractor import PDFExtractor
from patentmind.processing.cleaner import PatentTextCleaner
from patentmind.processing.chunker import PatentChunker
from patentmind.embeddings.vector_store import get_vector_store

load_dotenv()
console = Console()

PDF_BATCH_SIZE = 500  # Process 500 PDFs per worker batch iteration

def worker_process(worker_id: int, items: List[Tuple[str, str]], num_gpus: int, progress_queue: Optional[mp.Queue] = None):
    if not items:
        if progress_queue:
            progress_queue.put(None)
        return
        
    # Enforce GPU execution strictly on CDAC server if PyTorch is available
    if torch is not None and hasattr(torch, "cuda") and torch.cuda.is_available() and num_gpus > 0:
        gpu_id = worker_id % num_gpus
        device = f"cuda:{gpu_id}"
    else:
        device = "cpu"
    
    embedder = EmbeddingEncoder(device=device, strict_gpu=True)
    ocr_engine = get_glm_ocr_engine()
    chunker = PatentChunker()
    vector_store = get_vector_store()

    # Process items in sub-batches
    total_items = len(items)
    for batch_start in range(0, total_items, PDF_BATCH_SIZE):
        batch_items = items[batch_start:batch_start + PDF_BATCH_SIZE]

        for idx, (s3_key, patent_number) in enumerate(batch_items, 1):
            try:
                # 1. Per-patent double-check to skip already-indexed patents
                if hasattr(vector_store, "patent_exists") and vector_store.patent_exists(patent_number):
                    if progress_queue:
                        progress_queue.put((worker_id, 1, patent_number, "Skipped"))
                    continue

                if progress_queue:
                    progress_queue.put((worker_id, 0, patent_number, "Processing"))

                # 2. Download PDF
                pdf_bytes = s3_client.download_patent_pdf(s3_key)
                if not pdf_bytes:
                    if progress_queue:
                        progress_queue.put((worker_id, 1, patent_number, "Empty PDF"))
                    continue

                # 3. OCR & Extraction
                pages = PDFExtractor.extract_pages(pdf_bytes)
                full_text = []
                for page in pages:
                    if page.get("is_scanned", False):
                        full_text.append(ocr_engine.process_scanned_page(pdf_bytes, page["page_num"]))
                    else:
                        full_text.append(page["text"])

                raw_combined = "\n\n".join(full_text)
                cleaned_text = PatentTextCleaner.clean_text(raw_combined)

                # 4. Chunking
                chunks = chunker.chunk_patent(
                    patent_number=patent_number,
                    cleaned_text=cleaned_text,
                    s3_key=s3_key,
                    claims_text="S3 Direct Ingestion - Claims extracted from body"
                )

                chunk_texts = [c["chunk_text"] for c in chunks]
                embeddings_list = embedder.batch_encode(chunk_texts, batch_size=256)

                # 5. Qdrant Upsert
                if chunks:
                    vector_store.upsert(chunks=chunks, embeddings=embeddings_list)
                    
                if progress_queue:
                    progress_queue.put((worker_id, 1, patent_number, "Indexed"))

            except Exception as e:
                if progress_queue:
                    progress_queue.put((worker_id, 1, patent_number, f"Error: {e}"))
                    
    if progress_queue:
        progress_queue.put(None)

def progress_listener(progress: Progress, task_ids: dict, num_workers: int, progress_queue: mp.Queue):
    completed_workers = 0
    while completed_workers < num_workers:
        try:
            msg = progress_queue.get()
            if msg is None:
                completed_workers += 1
                continue
            worker_id, advance_count, patent_num, status = msg
            task_id = task_ids.get(worker_id)
            if task_id is not None:
                short_pn = patent_num[:20]
                progress.update(
                    task_id, 
                    advance=advance_count, 
                    description=f"[cyan]Worker {worker_id:02d}[/cyan] [{status}] {short_pn}"
                )
        except Exception:
            pass

def run_gpu_worker():
    console.print("[bold cyan]Starting 16-Core Strict GPU Worker Pipeline (Multi-Task Progress Display)...[/bold cyan]")
    
    # Check CUDA GPU availability
    if torch is None or not hasattr(torch, "cuda") or not torch.cuda.is_available():
        console.print("[bold yellow]Notice: CUDA GPU not detected on this host. Running 16 parallel workers in CPU mode...[/bold yellow]")
        num_gpus = 0
    else:
        num_gpus = torch.cuda.device_count()
        console.print(f"[bold green]Strict GPU Mode Enabled: Found {num_gpus} CUDA GPUs.[/bold green]")

    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not bucket_name:
        console.print("[red]S3_BUCKET_NAME not set in environment![/red]")
        return
        
    s3 = boto3.client('s3', 
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), 
        region_name=os.getenv('AWS_REGION')
    )

    console.print(f"[cyan]Scanning S3 Bucket: {bucket_name} for PDFs...[/cyan]")
    try:
        pdf_keys = []
        paginator = s3.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name):
            if 'Contents' in page:
                for obj in page['Contents']:
                    if obj['Key'].lower().endswith('.pdf'):
                        pdf_keys.append(obj['Key'])
                        
        if not pdf_keys:
            console.print("[yellow]Bucket contains 0 PDFs![/yellow]")
            return
            
        console.print(f"[bold green]Found {len(pdf_keys)} total PDFs in S3 to process.[/bold green]")
    except Exception as e:
        console.print(f"[red]Error scanning S3: {e}[/red]")
        return
    
    # Check existing indexed patents in Qdrant
    console.print("[cyan]Checking Qdrant vector index...[/cyan]")
    vector_store = get_vector_store()
    existing_patents = set()
    try:
        if hasattr(vector_store, "get_existing_patent_numbers"):
            existing_patents = vector_store.get_existing_patent_numbers()
    except Exception as e:
        console.print(f"[yellow]Skipping bulk existence check ({e}). Processing all S3 PDFs...[/yellow]")
    
    total_vectors = vector_store.get_vector_count()

    unindexed_items = []
    for s3_key in pdf_keys:
        pn = os.path.basename(s3_key).replace(".pdf", "").replace(".PDF", "")
        if pn not in existing_patents:
            unindexed_items.append((s3_key, pn))

    if not unindexed_items and total_vectors > 0:
        console.print(f"[bold green]✓ Qdrant already contains {total_vectors} vectors for all {len(pdf_keys)} patents. No new ingestion needed![/bold green]")
        return

    console.print(f"[cyan]Found {len(unindexed_items)} unindexed PDFs to process across 16 parallel workers.[/cyan]")

    num_workers = int(os.getenv("NUM_WORKERS", 16))
    
    # Partition unindexed PDFs across workers evenly
    chunks_partitioned = [[] for _ in range(num_workers)]
    for idx, item in enumerate(unindexed_items):
        chunks_partitioned[idx % num_workers].append(item)

    progress_queue = mp.Queue()

    console.print(f"[bold green]🚀 Launching Real-Time Multi-Worker Visual Progress Bars...[/bold green]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("{task.description}"),
        BarColumn(bar_width=30),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeRemainingColumn(),
        console=console,
        refresh_per_second=4
    ) as progress:
        task_ids = {}
        for w in range(num_workers):
            device_label = f"cuda:{w % num_gpus}" if num_gpus > 0 else "cpu"
            worker_total = len(chunks_partitioned[w])
            if worker_total > 0:
                task_ids[w] = progress.add_task(
                    f"[cyan]Worker {w:02d}[/cyan] ({device_label})", 
                    total=worker_total
                )

        # Start background listener thread for updating progress bars
        listener = threading.Thread(
            target=progress_listener, 
            args=(progress, task_ids, num_workers, progress_queue),
            daemon=True
        )
        listener.start()

        # Start 16 worker processes
        processes = []
        for worker_id in range(num_workers):
            p = mp.Process(
                target=worker_process,
                args=(worker_id, chunks_partitioned[worker_id], num_gpus, progress_queue)
            )
            p.start()
            processes.append(p)

        for p in processes:
            p.join()

        listener.join(timeout=2.0)

    console.print("\n[bold green]🎉 All 16 Workers Finished Processing All PDF Batches![/bold green]")

if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    run_gpu_worker()
