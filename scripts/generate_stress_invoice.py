from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "input"
PNG_PATH = OUTPUT_DIR / "stress_messy_invoice.png"
PDF_PATH = OUTPUT_DIR / "stress_messy_invoice.pdf"


def main() -> None:
    random.seed(42)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    image = build_invoice_image()
    image.save(PNG_PATH)
    write_pdf(image, PDF_PATH)
    print(f"created_png={PNG_PATH}")
    print(f"created_pdf={PDF_PATH}")


def build_invoice_image() -> Image.Image:
    width, height = 1240, 1754
    base = Image.new("RGB", (width, height), "#f7f0da")
    draw = ImageDraw.Draw(base)
    title_font = font(62, bold=True)
    heading_font = font(35, bold=True)
    body_font = font(30)
    tiny_font = font(22)

    draw_background(draw, width, height)
    draw_logo(draw)
    draw_header(draw, title_font, heading_font)
    draw_supplier_block(draw, body_font, tiny_font)
    draw_buyer_block(draw, body_font, tiny_font)
    draw_lines(draw, heading_font, body_font)
    draw_totals(draw, heading_font, body_font)
    draw_noise_text(draw, tiny_font)
    draw_watermarks(draw, width, height)
    draw_stamps(draw, heading_font)
    draw_occlusions(draw, width, height)

    base = add_noise(base)
    base = base.rotate(-2.4, expand=True, fillcolor="#eee6cc")
    base = base.filter(ImageFilter.GaussianBlur(radius=0.55))
    base = base.resize((width, height), Image.Resampling.BICUBIC)
    return base


def draw_background(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    for y in range(0, height, 8):
        shade = 238 + int(10 * math.sin(y / 90))
        draw.line((0, y, width, y), fill=(shade, max(220, shade - 12), 188), width=8)
    for x in range(-300, width, 160):
        draw.line((x, 0, x + 650, height), fill="#eadfbd", width=5)
    draw.rectangle((38, 42, width - 44, height - 55), outline="#b38a3b", width=5)
    draw.rectangle((56, 61, width - 63, height - 74), outline="#6e8ca8", width=2)


def draw_logo(draw: ImageDraw.ImageDraw) -> None:
    draw.ellipse((85, 85, 230, 230), fill="#22577a", outline="#ffbf69", width=8)
    draw.polygon([(155, 105), (202, 205), (106, 205)], fill="#ffbf69")
    draw.arc((110, 123, 202, 212), 200, 340, fill="#e63946", width=7)


def draw_header(draw: ImageDraw.ImageDraw, title_font: ImageFont.ImageFont, heading_font: ImageFont.ImageFont) -> None:
    draw.text((255, 86), "INVOICE", fill="#253047", font=title_font)
    draw.text((705, 162), "No: INV-MESS-2026-077", fill="#5b1a18", font=heading_font)
    draw.text((705, 214), "Date: 2026-05-06", fill="#4a5b1a", font=heading_font)
    draw.text((705, 266), "Currency: EUR", fill="#17324d", font=heading_font)
    draw.line((255, 158, 650, 158), fill="#db6b2f", width=10)


def draw_supplier_block(draw: ImageDraw.ImageDraw, body_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    draw.rounded_rectangle((90, 310, 555, 505), radius=18, fill="#fff3c7", outline="#d56b2f", width=5)
    draw.text((115, 330), "Supplier", fill="#6a1b1a", font=body_font)
    draw.text((115, 382), "Supplier: Messy Color Labs SARL", fill="#2a3240", font=tiny_font)
    draw.text((115, 425), "VAT ID: FR-MESS-009812", fill="#2a3240", font=tiny_font)
    draw.text((115, 468), "12 Rue Pixelisee, Tunis", fill="#2a3240", font=tiny_font)


def draw_buyer_block(draw: ImageDraw.ImageDraw, body_font: ImageFont.ImageFont, tiny_font: ImageFont.ImageFont) -> None:
    draw.rounded_rectangle((665, 310, 1145, 505), radius=18, fill="#dbefff", outline="#227c9d", width=5)
    draw.text((690, 330), "Client", fill="#12384a", font=body_font)
    draw.text((690, 382), "Client: Alpha Retail Group", fill="#2a3240", font=tiny_font)
    draw.text((690, 425), "PO: PO-7781-XY", fill="#2a3240", font=tiny_font)
    draw.text((690, 468), "Email: finance@example.test", fill="#2a3240", font=tiny_font)


def draw_lines(draw: ImageDraw.ImageDraw, heading_font: ImageFont.ImageFont, body_font: ImageFont.ImageFont) -> None:
    y = 585
    headers = [("Description", 110), ("Qty", 650), ("Unit", 760), ("Amount", 940)]
    draw.rectangle((85, y, 1155, y + 58), fill="#224b60")
    for label, x in headers:
        draw.text((x, y + 10), label, fill="#fefae0", font=heading_font)
    rows = [
        ("Color document analysis", "1", "420.00", "420.00"),
        ("Multi-format invoice extraction", "2", "315.00", "630.00"),
        ("VAT validation and anomaly report", "1", "250.00", "250.00"),
    ]
    y += 70
    for idx, row in enumerate(rows):
        fill = "#fffdf2" if idx % 2 == 0 else "#e9f5db"
        draw.rectangle((85, y, 1155, y + 72), fill=fill, outline="#7a7a55", width=2)
        draw.text((110, y + 19), row[0], fill="#20263a", font=body_font)
        draw.text((665, y + 19), row[1], fill="#20263a", font=body_font)
        draw.text((760, y + 19), row[2], fill="#20263a", font=body_font)
        draw.text((940, y + 19), row[3], fill="#20263a", font=body_font)
        y += 72


def draw_totals(draw: ImageDraw.ImageDraw, heading_font: ImageFont.ImageFont, body_font: ImageFont.ImageFont) -> None:
    x1, y1, x2, y2 = 645, 930, 1155, 1185
    draw.rounded_rectangle((x1, y1, x2, y2), radius=16, fill="#fff1e6", outline="#d62828", width=5)
    values = [
        ("Subtotal HT", "1300.00 EUR"),
        ("VAT 20%", "260.00 EUR"),
        ("Total", "1560.00 EUR"),
    ]
    y = y1 + 25
    for label, value in values:
        color = "#571c1c" if "Total" in label else "#253047"
        draw.text((x1 + 25, y), label + ":", fill=color, font=heading_font)
        draw.text((x1 + 300, y), value, fill=color, font=body_font)
        y += 70


def draw_noise_text(draw: ImageDraw.ImageDraw, tiny_font: ImageFont.ImageFont) -> None:
    notes = [
        "Payment due: 30 days",
        "IBAN: FR76 3000 6000 0112 3456 7890 189",
        "Some footer text overlaps after bad scan",
        "Discount: 0.00 EUR",
    ]
    y = 1230
    for note in notes:
        draw.text((105 + random.randint(-15, 15), y), note, fill="#5a5a66", font=tiny_font)
        y += 45


def draw_watermarks(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    watermark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    wdraw = ImageDraw.Draw(watermark)
    big = font(118, bold=True)
    for y in (560, 980):
        wdraw.text((210, y), "SCAN COPY", fill=(220, 30, 30, 42), font=big)
    rotated = watermark.rotate(-18, expand=False)
    draw.bitmap((0, 0), rotated, fill=None)


def draw_stamps(draw: ImageDraw.ImageDraw, heading_font: ImageFont.ImageFont) -> None:
    draw.ellipse((130, 965, 445, 1280), outline="#b51d1a", width=13)
    draw.text((182, 1080), "PAID?", fill="#b51d1a", font=heading_font)
    draw.line((105, 1390, 500, 1508), fill="#1d3557", width=9)
    draw.line((118, 1510, 475, 1382), fill="#1d3557", width=5)


def draw_occlusions(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    for _ in range(24):
        x = random.randint(80, width - 250)
        y = random.randint(520, height - 260)
        draw.rectangle((x, y, x + random.randint(45, 160), y + random.randint(8, 26)), fill=random.choice(["#ffffff", "#ffd166", "#a8dadc"]))
    draw.rectangle((865, 997, 1125, 1034), fill="#efe0b8")
    draw.line((83, 1188, 1145, 1167), fill="#6c757d", width=3)


def add_noise(image: Image.Image) -> Image.Image:
    pixels = image.load()
    width, height = image.size
    for _ in range(65000):
        x = random.randrange(width)
        y = random.randrange(height)
        r, g, b = pixels[x, y]
        delta = random.randint(-38, 38)
        pixels[x, y] = (
            max(0, min(255, r + delta)),
            max(0, min(255, g + delta)),
            max(0, min(255, b + delta)),
        )
    return image


def write_pdf(image: Image.Image, path: Path) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A4)
    page_width, page_height = A4
    pdf.drawImage(ImageReader(image), 0, 0, width=page_width, height=page_height)
    pdf.save()


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


if __name__ == "__main__":
    main()
