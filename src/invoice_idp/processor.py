from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Union

from .export import export_results
from .extraction import extract_text_from_pdf
from .models import Anomaly, InvoiceData, ProcessingResult
from .parsing import parse_invoice
from .validation import validate_invoice


PathLike = Union[str, Path]


def process_documents(
    input_path: PathLike,
    output_dir: PathLike = "data/output",
    ocr_language: str = "eng",
    force_ocr: bool = False,
) -> Dict[str, object]:
    pdfs = _collect_pdfs(Path(input_path))
    results = [process_pdf(path, ocr_language=ocr_language, force_ocr=force_ocr) for path in pdfs]
    exports = export_results(results, Path(output_dir))
    summary = {
        "processed": len(results),
        "ok": sum(1 for item in results if item.status == "OK"),
        "review": sum(1 for item in results if item.status == "REVIEW"),
        "exports": exports,
        "results": [item.to_json() for item in results],
    }
    summary_path = Path(output_dir) / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["exports"]["summary_json"] = str(summary_path)
    return summary


def process_pdf(pdf_path: PathLike, ocr_language: str = "eng", force_ocr: bool = False) -> ProcessingResult:
    path = Path(pdf_path)
    try:
        text, method = extract_text_from_pdf(path, ocr_language=ocr_language, force_ocr=force_ocr)
        invoice = parse_invoice(text, path.name, extraction_method=method)
        anomalies = validate_invoice(invoice)
        return ProcessingResult(invoice=invoice, anomalies=anomalies)
    except Exception as exc:
        invoice = InvoiceData(file_name=path.name, extraction_method="error")
        anomaly = Anomaly(
            file_name=path.name,
            field="pdf",
            extracted_value="",
            expected_value="readable PDF",
            severity="error",
            rule="processing_error",
            message=str(exc),
        )
        return ProcessingResult(invoice=invoice, anomalies=[anomaly])


def _collect_pdfs(path: Path) -> List[Path]:
    if path.is_file():
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Input file is not a PDF: {path}")
        return [path]
    if path.is_dir():
        pdfs = sorted(path.glob("*.pdf"))
        if not pdfs:
            raise ValueError(f"No PDF files found in: {path}")
        return pdfs
    raise FileNotFoundError(str(path))

