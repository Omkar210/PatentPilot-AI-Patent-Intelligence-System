"""
ingestion/pdf_downloader.py — Patent PDF Downloader & Storage

Downloads full-text PDF documents for given Patent IDs / URLs from public repositories
(Google Patents Storage, USPTO PIW) into a local directory (e.g., uploads/ or data/pdfs/).
"""

import os
import re
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

PDF_DIR = Path("uploads/pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)


def get_google_patent_pdf_url(patent_id: str) -> str:
    """
    Constructs or resolves Google Patents PDF URL for a given patent ID.
    Example Patent IDs: US10123456B2, US20210123456A1, US11234567B2
    """
    clean_id = patent_id.replace("-", "").replace(" ", "").upper()
    if not clean_id.startswith("US"):
        clean_id = f"US{clean_id}"
    
    # Direct Google Patents landing / download link structure
    return f"https://patentimages.storage.googleapis.com/pages/{clean_id}.pdf"


def download_patent_pdf(patent_id: str, pdf_url: Optional[str] = None) -> Optional[Path]:
    """
    Downloads the full patent PDF file for a patent_id and saves it locally.
    Returns the absolute local Path if successful, else None.
    """
    clean_id = patent_id.replace("-", "_").replace("/", "_")
    local_path = PDF_DIR / f"{clean_id}.pdf"

    if local_path.exists() and local_path.stat().st_size > 1000:
        return local_path

    urls_to_try = []
    if pdf_url:
        urls_to_try.append(pdf_url)
    
    # Google Patents PDF candidate URLs
    p_num = re.sub(r"[^A-Za-z0-9]", "", patent_id).upper()
    if not p_num.startswith("US"):
        p_num = f"US{p_num}"
    
    # Formats used by Google Patent storage
    urls_to_try.extend([
        f"https://patentimages.storage.googleapis.com/pdfs/{p_num}.pdf",
        f"https://patentimages.storage.googleapis.com/pages/{p_num}.pdf",
        f"https://patents.google.com/patent/{p_num}/en",
    ])

    client = httpx.Client(follow_redirects=True, timeout=20.0)
    for url in urls_to_try:
        try:
            r = client.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
            if r.status_code == 200 and r.headers.get("content-type", "").lower() == "application/pdf" or r.content.startswith(b"%PDF"):
                local_path.write_bytes(r.content)
                print(f"[PDF Downloader] Successfully downloaded PDF for {patent_id} -> {local_path} ({len(r.content)} bytes)")
                return local_path
            elif r.status_code == 200 and "application/pdf" not in r.headers.get("content-type", ""):
                # Try finding direct pdf link inside HTML page if landed on Google Patents HTML
                pdf_match = re.search(r'href="(https://patentimages\.storage\.googleapis\.com/[^"]+\.pdf)"', r.text)
                if pdf_match:
                    pdf_direct_url = pdf_match.group(1)
                    pdf_resp = client.get(pdf_direct_url)
                    if pdf_resp.status_code == 200 and pdf_resp.content.startswith(b"%PDF"):
                        local_path.write_bytes(pdf_resp.content)
                        print(f"[PDF Downloader] Extracted direct PDF for {patent_id} -> {local_path} ({len(pdf_resp.content)} bytes)")
                        return local_path
        except Exception as e:
            continue

    print(f"[PDF Downloader Warning] Could not download PDF for {patent_id}")
    return None


if __name__ == "__main__":
    # Smoke test with a real public patent: US11234567B2 or US10000000B2
    test_id = "US10000000B2"
    path = download_patent_pdf(test_id)
    if path:
        print(f"Verified PDF download: {path} (Size: {path.stat().st_size} bytes)")
