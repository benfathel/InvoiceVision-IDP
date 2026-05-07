from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple


InvoiceLines = List[Tuple[str, str]]


def generate_demo_pdfs(output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    invoices = [
        (
            "demo_01_valid.pdf",
            [
                ("Supplier", "Acme Office SARL"),
                ("Invoice No", "FAC-2026-001"),
                ("Date", "2026-04-30"),
                ("Subtotal HT", "1000.00 EUR"),
                ("TVA 20%", "200.00 EUR"),
                ("Total TTC", "1200.00 EUR"),
            ],
        ),
        (
            "demo_02_vat_mismatch.pdf",
            [
                ("Supplier", "Northwind Services"),
                ("Invoice No", "FAC-2026-002"),
                ("Date", "2026-04-29"),
                ("Subtotal HT", "1000.00 EUR"),
                ("TVA 20%", "180.00 EUR"),
                ("Total TTC", "1180.00 EUR"),
            ],
        ),
        (
            "demo_03_total_mismatch.pdf",
            [
                ("Supplier", "Delta Consulting"),
                ("Invoice No", "FAC-2026-003"),
                ("Date", "2026-04-28"),
                ("Subtotal HT", "800.00 EUR"),
                ("TVA 20%", "160.00 EUR"),
                ("Total TTC", "900.00 EUR"),
            ],
        ),
        (
            "demo_04_missing_supplier.pdf",
            [
                ("Invoice No", "FAC-2026-004"),
                ("Date", "2026-04-27"),
                ("Subtotal HT", "500.00 EUR"),
                ("TVA 20%", "100.00 EUR"),
                ("Total TTC", "600.00 EUR"),
            ],
        ),
    ]
    created = [_write_text_pdf(output_dir / name, lines) for name, lines in invoices]
    created.append(_write_ocr_pdf(output_dir / "demo_05_ocr_valid.pdf"))
    return created


def _write_text_pdf(path: Path, lines: InvoiceLines) -> Path:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("reportlab missing. Run: pip install -r requirements.txt") from exc

    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, height - 72, "Invoice")
    pdf.setFont("Helvetica", 12)
    y = height - 120
    for label, value in lines:
        pdf.drawString(72, y, f"{label}: {value}")
        y -= 26
    pdf.save()
    return path


def _write_ocr_pdf(path: Path) -> Path:
    try:
        from PIL import Image, ImageDraw, ImageFont
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError("Pillow/reportlab missing. Run: pip install -r requirements.txt") from exc

    lines = [
        "Invoice",
        "Supplier: OCR Supplies Ltd",
        "Invoice No: OCR-2026-005",
        "Date: 2026-04-26",
        "Subtotal HT: 300.00 EUR",
        "TVA 20%: 60.00 EUR",
        "Total TTC: 360.00 EUR",
    ]
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("Arial.ttf", 42)
    except OSError:
        font = ImageFont.load_default()
    y = 120
    for line in lines:
        draw.text((120, y), line, fill="black", font=font)
        y += 95

    pdf = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4
    pdf.drawImage(ImageReader(image), 36, 72, width=width - 72, height=height - 144, preserveAspectRatio=True)
    pdf.save()
    return path

