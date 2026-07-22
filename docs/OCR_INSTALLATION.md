# PaddleOCR Integration & Installation Guide — PatentPilot AI

PatentPilot AI uses **PaddleOCR** (PP-OCRv3 models via ONNX runtime engine `rapidocr-onnxruntime`) as the Stage 4 OCR fallback engine for scanned patent PDF pages.

---

## Architecture & Integration in Project Structure

```
PatentPilot AI/
├── ingestion/
│   └── ocr_fallback.py       ← Integrates PaddleOCR engine (RapidOCR / PP-OCRv3)
├── agents/
│   └── document_processing.py ← Stage 4 node: PyMuPDF + PaddleOCR fallback
└── scripts/
    └── extract_all_pdfs.py   ← Bulk PDF text extraction with OCR fallback
```

---

## Installation Commands

To install and verify PaddleOCR inside the project virtual environment:

### Step 1: Activate Virtual Environment

```powershell
# On Windows PowerShell
venv\Scripts\activate
```

### Step 2: Install Packages

```powershell
pip install rapidocr-onnxruntime pyclipper shapely --no-deps
```

### Step 3: Verify Installation

```powershell
python -c "from rapidocr_onnxruntime import RapidOCR; engine = RapidOCR(); print('✓ PaddleOCR engine initialized successfully!')"
```

---

## How It Works in Stage 4 Workflow

1. `PyMuPDF` (`fitz`) opens the patent PDF and extracts native text layers.
2. If a page has **near-empty text** (< 50 characters, indicating a scanned image page), `ingestion/ocr_fallback.py` renders the page to a high-resolution image (200 DPI).
3. `RapidOCR` runs PP-OCRv3 detection and recognition models to extract text from the scanned image page.
4. The extracted text is saved into the document's structured output in `data/extracted_documents/{patent_id}.json`.
