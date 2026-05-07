from __future__ import annotations

from decimal import Decimal
from typing import List

from .models import Anomaly, InvoiceData, decimal_to_text


DEFAULT_TOLERANCE = Decimal("0.02")


def validate_invoice(invoice: InvoiceData, tolerance: Decimal = DEFAULT_TOLERANCE) -> List[Anomaly]:
    anomalies: List[Anomaly] = []

    required_fields = {
        "supplier": invoice.supplier,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "total_ttc": invoice.total_ttc,
    }
    for field, value in required_fields.items():
        if value in (None, ""):
            anomalies.append(
                Anomaly(
                    file_name=invoice.file_name,
                    file_id=invoice.file_id,
                    field=field,
                    extracted_value="",
                    expected_value="present",
                    severity="error",
                    rule="required_field",
                    message=f"Required field missing: {field}",
                )
            )

    if invoice.subtotal_ht is not None and invoice.vat_amount is not None and invoice.total_ttc is not None:
        expected_total = invoice.subtotal_ht + invoice.vat_amount
        if _outside_tolerance(expected_total, invoice.total_ttc, tolerance):
            anomalies.append(
                Anomaly(
                    file_name=invoice.file_name,
                    file_id=invoice.file_id,
                    field="total_ttc",
                    extracted_value=decimal_to_text(invoice.total_ttc),
                    expected_value=decimal_to_text(expected_total),
                    severity="error",
                    rule="total_match",
                    message="Total differs from subtotal plus VAT",
                )
            )

    if invoice.subtotal_ht is not None and invoice.vat_rate is not None and invoice.vat_amount is not None:
        expected_vat = (invoice.subtotal_ht * invoice.vat_rate / Decimal("100")).quantize(Decimal("0.01"))
        if _outside_tolerance(expected_vat, invoice.vat_amount, tolerance):
            anomalies.append(
                Anomaly(
                    file_name=invoice.file_name,
                    file_id=invoice.file_id,
                    field="vat_amount",
                    extracted_value=decimal_to_text(invoice.vat_amount),
                    expected_value=decimal_to_text(expected_vat),
                    severity="error",
                    rule="vat_rate_match",
                    message="VAT amount differs from subtotal times VAT rate",
                )
            )

    if invoice.total_ttc is not None and invoice.total_ttc < 0:
        anomalies.append(
            Anomaly(
                file_name=invoice.file_name,
                file_id=invoice.file_id,
                field="total_ttc",
                extracted_value=decimal_to_text(invoice.total_ttc),
                expected_value=">= 0",
                severity="error",
                rule="positive_total",
                message="Total is negative",
            )
        )

    if invoice.confidence is not None and invoice.confidence < Decimal("0.70"):
        anomalies.append(
            Anomaly(
                file_name=invoice.file_name,
                file_id=invoice.file_id,
                field="confidence",
                extracted_value=decimal_to_text(invoice.confidence),
                expected_value=">= 0.70",
                severity="warning",
                rule="low_confidence",
                message="Low LLM confidence, human review recommended",
            )
        )

    return anomalies


def _outside_tolerance(expected: Decimal, actual: Decimal, tolerance: Decimal) -> bool:
    return abs(expected - actual) > tolerance
