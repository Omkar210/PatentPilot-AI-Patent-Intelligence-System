"""
scripts/extract_all_pdfs.py — Extract & Save Structured Text for Every Downloaded Patent PDF

Iterates over all downloaded patent PDFs in uploads/pdfs/, extracts:
- Full page-by-page text with OCR fallback for scanned pages
- Abstract section
- Claims section
- Inventors / Patent metadata
- Total page count & character count

Saves individual JSON files for each document into data/extracted_documents/{patent_id}.json
and an index summary to data/extracted_documents_index.json.
"""

import json
import re
import sys
from pathlib import Path
import fitz  # PyMuPDF

sys.path.insert(0, ".")
from ingestion.ocr_fallback import extract_page_ocr

PDF_DIR = Path("uploads/pdfs")
EXTRACTED_DIR = Path("data/extracted_documents")
EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)


def parse_patent_pdf(pdf_path: Path) -> dict:
    """Extracts structured sections and text from a patent PDF using PyMuPDF + OCR fallback."""
    doc = fitz.open(pdf_path)
    patent_id = pdf_path.stem
    
    pages_text = []
    full_text_list = []
    
    for i, page in enumerate(doc):
        text = page.get_text("text")
        # If page has near-empty text (scanned image page), apply OCR fallback
        if len(text.strip()) < 50:
            ocr_text = extract_page_ocr(page)
            if len(ocr_text.strip()) > len(text.strip()):
                text = ocr_text

        pages_text.append({
            "page_number": i + 1,
            "text": text,
            "char_count": len(text)
        })
        full_text_list.append(text)
        
    doc.close()
    
    full_text = "\n".join(full_text_list)
    
    # Simple regex extraction for key sections
    abstract_match = re.search(r"\(57\)\s*ABSTRACT\s*(.*?)(?=\(\d+\)|Claims|FIELD|BACKGROUND|\Z)", full_text, re.DOTALL | re.IGNORECASE)
    abstract = abstract_match.group(1).strip() if abstract_match else full_text[:1500]
    
    claims_match = re.search(r"(What is claimed is:|CLAIMS|We claim:)(.*?)(?=DESCRIPTION|DETAILED DESCRIPTION|\Z)", full_text, re.DOTALL | re.IGNORECASE)
    claims = claims_match.group(2).strip() if claims_match else ""
    
    title_match = re.search(r"\(54\)\s*([A-Z0-9\s,\-\.\(\)]+)", full_text)
    title = title_match.group(1).strip() if title_match else patent_id
    
    inventors_match = re.search(r"\(72\)\s*Inventor[s]?:?\s*(.*?)(?=\(73\)|\(71\)|\(74\)|\Z)", full_text, re.DOTALL)
    inventors_str = inventors_match.group(1).strip() if inventors_match else ""
    inventors = [i.strip() for i in re.split(r";|\n", inventors_str) if i.strip()][:5]

    return {
        "patent_id": patent_id,
        "title": title,
        "pdf_filename": pdf_path.name,
        "pdf_path": str(pdf_path),
        "total_pages": len(pages_text),
        "total_characters": len(full_text),
        "abstract": abstract,
        "inventors": inventors,
        "claims_summary": claims[:2000] if claims else "",
        "full_text": full_text,
        "pages": pages_text
    }


def main():
    print("=== Extracting & Saving Information for Every Patent PDF (with OCR Fallback) ===")
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files in {PDF_DIR}\n")
    
    summary_index = []
    
    for i, pdf_path in enumerate(pdf_files, start=1):
        try:
            extracted_data = parse_patent_pdf(pdf_path)
            patent_id = extracted_data["patent_id"]
            
            # Save individual JSON document file
            out_file = EXTRACTED_DIR / f"{patent_id}.json"
            out_file.write_text(json.dumps(extracted_data, indent=2, ensure_ascii=False), encoding="utf-8")
            
            summary_index.append({
                "patent_id": patent_id,
                "title": extracted_data["title"],
                "total_pages": extracted_data["total_pages"],
                "total_characters": extracted_data["total_characters"],
                "extracted_file": str(out_file)
            })
            print(f"[{i}/{len(pdf_files)}] Extracted {patent_id} ({extracted_data['total_pages']} pages, {extracted_data['total_characters']} chars) -> {out_file}")
        except Exception as e:
            print(f"[{i}/{len(pdf_files)}] Error extracting {pdf_path.name}: {e}")

    index_file = EXTRACTED_DIR.parent / "extracted_documents_index.json"
    index_file.write_text(json.dumps(summary_index, indent=2), encoding="utf-8")
    
    print("\n=======================================================")
    print(f"✓ Total Documents Processed & Saved: {len(summary_index)}")
    print(f"✓ Individual Extracted JSON Files: {EXTRACTED_DIR}")
    print(f"✓ Master Index File: {index_file}")
    print("=======================================================")


if __name__ == "__main__":
    main()
