from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional


def decimal_to_text(value: Optional[Decimal]) -> str:
    if value is None:
        return ""
    return f"{value.quantize(Decimal('0.01'))}"


def decimal_to_json(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    return decimal_to_text(value)


@dataclass
class InvoiceData:
    file_name: str
    file_id: str = ""
    supplier: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    subtotal_ht: Optional[Decimal] = None
    vat_rate: Optional[Decimal] = None
    vat_amount: Optional[Decimal] = None
    total_ttc: Optional[Decimal] = None
    currency: str = "EUR"
    raw_text_chars: int = 0
    extraction_method: str = "text"
    line_items: List[Dict[str, Any]] = field(default_factory=list)
    confidence: Optional[Decimal] = None
    missing_fields: List[str] = field(default_factory=list)

    def to_export_row(self, status: str) -> Dict[str, str]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "supplier": self.supplier or "",
            "invoice_number": self.invoice_number or "",
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else "",
            "subtotal_ht": decimal_to_text(self.subtotal_ht),
            "vat_rate": decimal_to_text(self.vat_rate),
            "vat_amount": decimal_to_text(self.vat_amount),
            "total_ttc": decimal_to_text(self.total_ttc),
            "currency": self.currency,
            "status": status,
            "extraction_method": self.extraction_method,
            "confidence": decimal_to_text(self.confidence),
            "missing_fields": ", ".join(self.missing_fields),
            "line_items_json": json.dumps(_json_safe(self.line_items), ensure_ascii=False),
        }

    def to_json(self) -> Dict[str, Any]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "supplier": self.supplier,
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date.isoformat() if self.invoice_date else None,
            "subtotal_ht": decimal_to_json(self.subtotal_ht),
            "vat_rate": decimal_to_json(self.vat_rate),
            "vat_amount": decimal_to_json(self.vat_amount),
            "total_ttc": decimal_to_json(self.total_ttc),
            "currency": self.currency,
            "raw_text_chars": self.raw_text_chars,
            "extraction_method": self.extraction_method,
            "line_items": _json_safe(self.line_items),
            "confidence": decimal_to_json(self.confidence),
            "missing_fields": self.missing_fields,
        }


@dataclass
class Anomaly:
    file_name: str
    field: str
    extracted_value: str
    expected_value: str
    severity: str
    rule: str
    message: str
    file_id: str = ""

    def to_row(self) -> Dict[str, str]:
        return {
            "file_id": self.file_id,
            "file_name": self.file_name,
            "field": self.field,
            "extracted_value": self.extracted_value,
            "expected_value": self.expected_value,
            "severity": self.severity,
            "rule": self.rule,
            "message": self.message,
        }


@dataclass
class ProcessingResult:
    invoice: InvoiceData
    anomalies: List[Anomaly] = field(default_factory=list)

    @property
    def status(self) -> str:
        return "OK" if not self.anomalies else "REVIEW"

    def to_json(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "invoice": self.invoice.to_json(),
            "anomalies": [item.to_row() for item in self.anomalies],
        }


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_to_json(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
