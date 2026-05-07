from __future__ import annotations

import io
from pathlib import Path
from typing import Tuple


def extract_text_from_pdf(
    pdf_path: Path,
    ocr_language: str = "eng",
    force_ocr: bool = False,
    min_text_chars: int = 40,
) -> Tuple[str, str]:
    """Extract text with embedded PDF text first, OCR fallback second."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF missing. Run: pip install -r requirements.txt") from exc

    doc = fitz.open(str(pdf_path))
    try:
        text = "\n".join(page.get_text("text") for page in doc).strip()
        if text and not force_ocr and len(text) >= min_text_chars:
            return text, "text"
        ocr_text = _ocr_document(doc, ocr_language).strip()
        if ocr_text:
            return ocr_text, "ocr"
        return text, "text"
    finally:
        doc.close()


def _ocr_document(doc, ocr_language: str) -> str:
    try:
        import fitz
        from PIL import Image
        import pytesseract
    except ImportError as exc:
        raise RuntimeError("OCR dependencies missing. Run: pip install -r requirements.txt") from exc

    pages = []
    matrix = fitz.Matrix(2, 2)
    for page in doc:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png")))
        pages.append(pytesseract.image_to_string(image, lang=ocr_language))
    return "\n".join(pages)
