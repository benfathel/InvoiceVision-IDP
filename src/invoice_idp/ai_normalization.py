from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import InvoiceData


def normalize_ai_invoice(payload: Any, file_name: str, file_id: str = "") -> InvoiceData:
    data = _unwrap_payload(payload)
    line_items = _normalize_line_items(data.get("line_items"))
    missing_fields = _normalize_missing_fields(data.get("missing_fields"))

    return InvoiceData(
        file_id=str(file_id or ""),
        file_name=Path(file_name).name,
        supplier=_clean_optional_text(data.get("supplier")),
        invoice_number=_clean_optional_text(data.get("invoice_number")),
        invoice_date=_parse_date(data.get("invoice_date")),
        subtotal_ht=_parse_decimal(data.get("subtotal_ht")),
        vat_rate=_parse_decimal(data.get("vat_rate")),
        vat_amount=_parse_decimal(data.get("vat_amount")),
        total_ttc=_parse_decimal(data.get("total_ttc")),
        currency=(_clean_optional_text(data.get("currency")) or "EUR").upper(),
        extraction_method="llm",
        line_items=line_items,
        confidence=_parse_decimal(data.get("confidence")),
        missing_fields=missing_fields,
    )


def _unwrap_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return {}
    if not isinstance(payload, dict):
        return {}

    for key in ("extracted_invoice", "output", "json", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return _unwrap_payload(value)
        if isinstance(value, str):
            parsed = _unwrap_payload(value)
            if parsed:
                return parsed
    return payload


def _normalize_line_items(value: Any) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        items.append(
            {
                "description": _clean_optional_text(item.get("description")) or "",
                "quantity": _decimal_to_string(_parse_decimal(item.get("quantity"))),
                "unit_price": _decimal_to_string(_parse_decimal(item.get("unit_price"))),
                "amount": _decimal_to_string(_parse_decimal(item.get("amount"))),
            }
        )
    return items


def _normalize_missing_fields(value: Any) -> List[str]:
    if isinstance(value, str):
        value = [part.strip() for part in value.split(",")]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_date(value: Any) -> Optional[date]:
    if isinstance(value, date):
        return value
    if value in (None, ""):
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%m/%d/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_decimal(value: Any) -> Optional[Decimal]:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if value in (None, ""):
        return None
    cleaned = str(value).replace("\u00a0", " ").strip()
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


def _clean_optional_text(value: Any) -> Optional[str]:
    if value in (None, ""):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip(" \t:-")
    return text or None


def _decimal_to_string(value: Optional[Decimal]) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'))}"
