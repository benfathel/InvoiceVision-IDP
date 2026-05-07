from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from .models import InvoiceData


CURRENCY_MAP = {
    "EUR": "EUR",
    "USD": "USD",
    "TND": "TND",
    "€": "EUR",
    "$": "USD",
}


def parse_invoice(text: str, file_name: str, extraction_method: str = "text") -> InvoiceData:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    supplier = _find_supplier(lines)
    invoice_number = _find_invoice_number(text)
    invoice_date = _find_date(text)
    subtotal = _find_labeled_amount(lines, [r"total\s+ht", r"subtotal", r"sous[- ]?total", r"montant\s+ht"])
    vat_rate = _find_vat_rate(text)
    vat_amount = _find_labeled_amount(lines, [r"\btva\b", r"\bvat\b"])
    total = _find_labeled_amount(
        lines,
        [r"total\s+ttc", r"grand\s+total", r"total\s+due", r"total\s+a\s+payer", r"\btotal\b"],
        exclude=[r"total\s+ht", r"subtotal", r"sous[- ]?total"],
    )
    currency = _find_currency(text)

    return InvoiceData(
        file_name=Path(file_name).name,
        supplier=supplier,
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        subtotal_ht=subtotal,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        total_ttc=total,
        currency=currency,
        raw_text_chars=len(text),
        extraction_method=extraction_method,
    )


def _find_supplier(lines: Sequence[str]) -> Optional[str]:
    for line in lines:
        match = re.search(r"\b(?:fournisseur|supplier|vendor)\b\s*[:\-]\s*(.+)$", line, re.I)
        if match:
            value = _clean_text(match.group(1))
            return value or None

    ignored = re.compile(r"\b(invoice|facture|date|total|tva|vat|subtotal|montant)\b", re.I)
    for line in lines[:6]:
        if not ignored.search(line) and len(line) >= 3:
            return _clean_text(line)
    return None


def _find_invoice_number(text: str) -> Optional[str]:
    patterns = [
        r"\b(?:facture|invoice)[ \t]*(?:no|n[°o.]?|number|#)[ \t]*[:\-]?[ \t]*([A-Z0-9][A-Z0-9\-\/_.]+)",
        r"\b(?:numero|number)[ \t]*(?:de[ \t]*)?(?:facture|invoice)?[ \t]*[:\-][ \t]*([A-Z0-9][A-Z0-9\-\/_.]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return _clean_text(match.group(1)).upper()
    return None


def _find_date(text: str) -> Optional[date]:
    label_match = re.search(
        r"\b(?:date|invoice\s+date|date\s+facture)\b\s*[:\-]?\s*([0-9]{1,4}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4})",
        text,
        re.I,
    )
    candidates = [label_match.group(1)] if label_match else []
    candidates.extend(re.findall(r"\b[0-9]{1,4}[\/\-.][0-9]{1,2}[\/\-.][0-9]{2,4}\b", text))
    for value in candidates:
        parsed = _parse_date(value)
        if parsed:
            return parsed
    return None


def _parse_date(value: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _find_vat_rate(text: str) -> Optional[Decimal]:
    match = re.search(r"\b(?:tva|vat)\b[^\n%]{0,30}?([0-9]{1,2}(?:[.,][0-9]+)?)\s*%", text, re.I)
    if not match:
        return None
    return _parse_decimal(match.group(1))


def _find_labeled_amount(
    lines: Sequence[str],
    include: Iterable[str],
    exclude: Iterable[str] = (),
) -> Optional[Decimal]:
    include_patterns = [re.compile(pattern, re.I) for pattern in include]
    exclude_patterns = [re.compile(pattern, re.I) for pattern in exclude]
    for line in lines:
        if not any(pattern.search(line) for pattern in include_patterns):
            continue
        if any(pattern.search(line) for pattern in exclude_patterns):
            continue
        candidates = _amount_candidates(line)
        if candidates:
            return candidates[-1]
    return None


def _amount_candidates(line: str) -> List[Decimal]:
    values: List[Decimal] = []
    for match in re.finditer(r"(?<![A-Z0-9])([+-]?\d[\d\s.,]*)(?![A-Z0-9])", line, re.I):
        after = line[match.end() :].lstrip()
        if after.startswith("%"):
            continue
        parsed = _parse_decimal(match.group(1))
        if parsed is not None:
            values.append(parsed)
    return values


def _parse_decimal(value: str) -> Optional[Decimal]:
    cleaned = value.replace("\u00a0", " ").strip()
    cleaned = re.sub(r"[^0-9,.\-+]", "", cleaned)
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _find_currency(text: str) -> str:
    match = re.search(r"\b(EUR|USD|TND)\b|[€$]", text, re.I)
    if not match:
        return "EUR"
    value = match.group(0).upper()
    return CURRENCY_MAP.get(value, "EUR")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" \t:-")
