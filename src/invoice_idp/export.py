from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

from .models import Anomaly, ProcessingResult


INVOICE_COLUMNS = [
    "file_id",
    "file_name",
    "supplier",
    "invoice_number",
    "invoice_date",
    "subtotal_ht",
    "vat_rate",
    "vat_amount",
    "total_ttc",
    "currency",
    "status",
    "extraction_method",
    "confidence",
    "missing_fields",
    "line_items_json",
]

ANOMALY_COLUMNS = [
    "file_id",
    "file_name",
    "field",
    "extracted_value",
    "expected_value",
    "severity",
    "rule",
    "message",
]


def export_results(results: Iterable[ProcessingResult], output_dir: Path) -> Dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_list = list(results)
    invoice_rows = [item.invoice.to_export_row(item.status) for item in result_list]
    anomaly_rows: List[Dict[str, str]] = []
    for item in result_list:
        anomaly_rows.extend(anomaly.to_row() for anomaly in item.anomalies)

    invoices_csv = output_dir / "invoices.csv"
    anomalies_csv = output_dir / "anomalies.csv"
    invoices_xlsx = output_dir / "invoices.xlsx"
    anomalies_xlsx = output_dir / "anomalies.xlsx"

    _write_csv(invoices_csv, INVOICE_COLUMNS, invoice_rows)
    _write_csv(anomalies_csv, ANOMALY_COLUMNS, anomaly_rows)
    _write_xlsx(invoices_xlsx, "Invoices", INVOICE_COLUMNS, invoice_rows)
    _write_xlsx(anomalies_xlsx, "Anomalies", ANOMALY_COLUMNS, anomaly_rows)

    return {
        "invoices_csv": str(invoices_csv),
        "anomalies_csv": str(anomalies_csv),
        "invoices_xlsx": str(invoices_xlsx),
        "anomalies_xlsx": str(anomalies_xlsx),
    }


def upsert_result(result: ProcessingResult, output_dir: Path) -> Dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    invoices_csv = output_dir / "invoices.csv"
    anomalies_csv = output_dir / "anomalies.csv"
    invoices_xlsx = output_dir / "invoices.xlsx"
    anomalies_xlsx = output_dir / "anomalies.xlsx"
    summary_path = output_dir / "summary.json"

    key = result.invoice.file_id or result.invoice.file_name
    invoice_rows = [
        row
        for row in _read_csv(invoices_csv)
        if (row.get("file_id") or row.get("file_name")) != key
    ]
    anomaly_rows = [
        row
        for row in _read_csv(anomalies_csv)
        if (row.get("file_id") or row.get("file_name")) != key
    ]

    invoice_rows.append(result.invoice.to_export_row(result.status))
    anomaly_rows.extend(anomaly.to_row() for anomaly in result.anomalies)

    _write_csv(invoices_csv, INVOICE_COLUMNS, invoice_rows)
    _write_csv(anomalies_csv, ANOMALY_COLUMNS, anomaly_rows)
    _write_xlsx(invoices_xlsx, "Invoices", INVOICE_COLUMNS, invoice_rows)
    _write_xlsx(anomalies_xlsx, "Anomalies", ANOMALY_COLUMNS, anomaly_rows)

    summary = {
        "processed": len(invoice_rows),
        "ok": sum(1 for row in invoice_rows if row.get("status") == "OK"),
        "review": sum(1 for row in invoice_rows if row.get("status") == "REVIEW"),
        "exports": {
            "invoices_csv": str(invoices_csv),
            "anomalies_csv": str(anomalies_csv),
            "invoices_xlsx": str(invoices_xlsx),
            "anomalies_xlsx": str(anomalies_xlsx),
            "summary_json": str(summary_path),
        },
    }
    import json

    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _write_csv(path: Path, columns: List[str], rows: List[Dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _write_xlsx(path: Path, sheet_name: str, columns: List[str], rows: List[Dict[str, str]]) -> None:
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl missing. Run: pip install -r requirements.txt") from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(columns)
    for row in rows:
        sheet.append([row.get(column, "") for column in columns])
    for column_cells in sheet.columns:
        max_len = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_cells[0].column_letter].width = min(max(max_len + 2, 12), 45)
    workbook.save(path)
