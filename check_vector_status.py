import os
import sys
import boto3
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

# Ensure root directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from patentmind.storage.s3_client import s3_client
from patentmind.embeddings.vector_store import get_vector_store

load_dotenv()
console = Console()

def check_status():
    console.print("[bold cyan]Checking Patent Vectorization Status...[/bold cyan]\n")
    
    # 1. Scan S3 bucket for all PDFs
    bucket_name = os.getenv("S3_BUCKET_NAME")
    pdf_keys = []
    if bucket_name:
        try:
            s3 = boto3.client('s3', 
                aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'), 
                aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'), 
                region_name=os.getenv('AWS_REGION')
            )
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=bucket_name):
                if 'Contents' in page:
                    for obj in page['Contents']:
                        if obj['Key'].lower().endswith('.pdf'):
                            pdf_keys.append(obj['Key'])
        except Exception as e:
            console.print(f"[red]S3 Scan Error: {e}[/red]")
            
    s3_patent_numbers = {os.path.basename(k).replace(".pdf", "").replace(".PDF", "") for k in pdf_keys}
    
    # 2. Query Qdrant Vector Engine
    console.print("[dim]Fetching vector metrics from Qdrant...[/dim]")
    vector_store = get_vector_store()
    total_vectors = vector_store.get_vector_count()
    indexed_patents = vector_store.get_existing_patent_numbers()
    
    unindexed = s3_patent_numbers - indexed_patents
    
    # 3. Render Summary Dashboard
    table = Table(title="📊 Patent Vectorization Status Summary", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right", style="bold green")
    
    table.add_row("Total Physical PDFs in AWS S3", str(len(s3_patent_numbers)))
    table.add_row("Total Vector Points in Qdrant Collection", f"{total_vectors:,}")
    table.add_row("Unique Patents Fully Vectorized & Stored", str(len(indexed_patents)))
    table.add_row("Unindexed / Remaining PDFs", str(len(unindexed)))
    
    console.print("\n")
    console.print(table)
    
    if not unindexed and len(s3_patent_numbers) > 0:
        console.print("\n[bold green]🎉 SUCCESS: 100% of all patents in S3 have been converted into vectors and stored in Qdrant![/bold green]\n")
    elif unindexed:
        console.print(f"\n[bold yellow]⚠️ Status: {len(unindexed)} PDFs remaining to be vectorized. Run 'python gpu_worker.py' to finish the remaining batch.[/bold yellow]\n")

if __name__ == "__main__":
    check_status()
