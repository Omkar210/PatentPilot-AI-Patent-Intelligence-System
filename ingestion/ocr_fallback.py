"""
ingestion/ocr_fallback.py — OCR Fallback Engine for Scanned Patent PDFs

When PyMuPDF extracts near-empty text from a PDF page (scanned image page),
this module renders the page to an image and uses Tesseract / PaddleOCR / OpenCV
to extract full text.
"""

import io
import fitz  # PyMuPDF
from PIL import Image


def extract_page_ocr(page: fitz.Page) -> str:
    """Renders a PDF page to pixmap image and applies OCR fallback."""
    try:
        # Render page to high-res image (300 DPI)
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))

        # Try PaddleOCR if available
        try:
            from paddleocr import PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            res = ocr.ocr(img_bytes, cls=True)
            lines = []
            if res and res[0]:
                for line in res[0]:
                    lines.append(line[1][0])
            return "\n".join(lines)
        except Exception:
            pass

        # Try pytesseract if available
        try:
            import pytesseract
            return pytesseract.image_to_string(img)
        except Exception:
            pass

        # Fallback basic text notification if OCR tools unavailable
        return f"[Scanned Image Page - {pix.width}x{pix.height}px]"
    except Exception as e:
        return f"[OCR Error: {e}]"
