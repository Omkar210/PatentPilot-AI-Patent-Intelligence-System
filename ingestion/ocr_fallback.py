"""
ingestion/ocr_fallback.py — OCR Fallback Engine for Scanned Patent PDFs

Provides module-level singleton initialization for PaddleOCR / RapidOCR and text extraction
from PDF files, Path objects, and raw image/PDF bytes.
"""

import logging
from pathlib import Path
from typing import Union, Optional, List
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)

_ocr_engine = None
_ocr_engine_type: Optional[str] = None  # "paddleocr" | "rapidocr" | None


def get_ocr_engine():
    """
    Module-level singleton initializer for OCR engine.
    Tries PaddleOCR first, then RapidOCR as secondary fallback.
    Returns the engine instance or False if unavailable.
    """
    global _ocr_engine, _ocr_engine_type
    if _ocr_engine is not None:
        return _ocr_engine

    # 1. Try PaddleOCR
    try:
        from paddleocr import PaddleOCR
        _ocr_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        _ocr_engine_type = "paddleocr"
        logger.info("PaddleOCR engine initialized successfully.")
        return _ocr_engine
    except Exception as e:
        logger.info(f"PaddleOCR unavailable: {e}. Trying RapidOCR fallback...")

    # 2. Try RapidOCR
    try:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
        _ocr_engine_type = "rapidocr"
        logger.info("RapidOCR engine initialized successfully.")
        return _ocr_engine
    except Exception as e:
        logger.warning(f"RapidOCR unavailable: {e}. OCR fallback disabled.")

    _ocr_engine = False
    _ocr_engine_type = None
    return _ocr_engine


def get_ocr_engine_type() -> Optional[str]:
    """Returns the type of active OCR engine ('paddleocr', 'rapidocr', or None)."""
    get_ocr_engine()
    return _ocr_engine_type


def extract_text_from_image_bytes(img_bytes: bytes) -> str:
    """Applies OCR engine to raw image bytes and returns extracted text."""
    if not img_bytes:
        return ""
    engine = get_ocr_engine()
    if not engine:
        return ""

    try:
        if _ocr_engine_type == "rapidocr":
            result, elapsed = engine(img_bytes)
            if result:
                lines = [
                    line[1]
                    for line in result
                    if line and len(line) > 1 and isinstance(line[1], str)
                ]
                return "\n".join(lines)
        elif _ocr_engine_type == "paddleocr":
            result = engine.ocr(img_bytes, cls=True)
            lines = []
            if result and isinstance(result, list):
                for res in result:
                    if res:
                        for line in res:
                            if line and len(line) > 1:
                                text_val = line[1][0] if isinstance(line[1], (tuple, list)) else line[1]
                                if isinstance(text_val, str):
                                    lines.append(text_val)
            return "\n".join(lines)
    except Exception as e:
        logger.warning(f"OCR execution failed on image bytes: {e}")

    return ""


def extract_text_ocr(pdf_path_or_image_bytes: Union[str, Path, bytes]) -> str:
    """
    Extracts text using OCR from a PDF path, Path object, or raw bytes (PDF/image).

    Args:
        pdf_path_or_image_bytes: File path (str/Path) or raw bytes.

    Returns:
        Extracted text string. Returns empty string if extraction fails or OCR unavailable.
    """
    if not pdf_path_or_image_bytes:
        return ""

    engine = get_ocr_engine()
    if not engine:
        return ""

    try:
        doc = None
        if isinstance(pdf_path_or_image_bytes, (str, Path)):
            path_obj = Path(pdf_path_or_image_bytes)
            if not path_obj.exists() or not path_obj.is_file():
                logger.warning(f"OCR file path does not exist: {path_obj}")
                return ""
            doc = fitz.open(path_obj)
        elif isinstance(pdf_path_or_image_bytes, bytes):
            if pdf_path_or_image_bytes.startswith(b"%PDF"):
                doc = fitz.open(stream=pdf_path_or_image_bytes, filetype="pdf")
            else:
                # Direct image bytes
                return extract_text_from_image_bytes(pdf_path_or_image_bytes)

        if doc is not None:
            extracted_pages: List[str] = []
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                page_text = extract_text_from_image_bytes(img_bytes)
                if page_text.strip():
                    extracted_pages.append(page_text.strip())
            doc.close()
            return "\n\n".join(extracted_pages)

    except Exception as e:
        logger.error(f"extract_text_ocr exception: {e}")

    return ""


def extract_page_ocr(page: fitz.Page) -> str:
    """Renders a PDF page to pixmap image and applies OCR fallback."""
    try:
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        ocr_text = extract_text_from_image_bytes(img_bytes)
        if ocr_text.strip():
            return ocr_text.strip()
        return page.get_text("text")
    except Exception as e:
        return f"[OCR Error: {e}]"
