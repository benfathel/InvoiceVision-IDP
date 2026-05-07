from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from .ai_normalization import normalize_ai_invoice
from .export import upsert_result
from .models import ProcessingResult
from .validation import validate_invoice


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIExtractionError(RuntimeError):
    pass


def process_openai_invoice(
    pdf_path: Path,
    file_id: str,
    file_name: str,
    output_dir: Path,
    model: Optional[str] = None,
) -> Dict[str, object]:
    extracted = extract_invoice_with_openai(pdf_path, model=model)
    invoice = normalize_ai_invoice(extracted, file_name=file_name, file_id=file_id)
    invoice.extraction_method = "openai_vision"
    anomalies = validate_invoice(invoice)
    result = ProcessingResult(invoice=invoice, anomalies=anomalies)
    summary = upsert_result(result, output_dir)
    payload = result.to_json()
    payload["openai"] = {
        "model": model or os.getenv("OPENAI_INVOICE_MODEL", "gpt-5-mini"),
        "pages_sent": len(render_pdf_pages_as_data_urls(pdf_path)),
    }
    payload["exports"] = summary["exports"]
    payload["aggregate"] = {
        "processed": summary["processed"],
        "ok": summary["ok"],
        "review": summary["review"],
    }
    return payload


def extract_invoice_with_openai(pdf_path: Path, model: Optional[str] = None) -> Dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise OpenAIExtractionError("OPENAI_API_KEY is not set in the Python service environment.")

    page_images = render_pdf_pages_as_data_urls(pdf_path)
    if not page_images:
        raise OpenAIExtractionError("Could not render PDF pages for OpenAI vision input.")

    request_body = {
        "model": model or os.getenv("OPENAI_INVOICE_MODEL", "gpt-5-mini"),
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are an expert invoice extraction system. Read invoice images directly. "
                            "Return JSON only. Extract visible values exactly when possible. "
                            "Use null for uncertain or missing scalar fields. Amounts must be numeric."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Extract the invoice fields from these page images as JSON.",
                    },
                    *[
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": "high",
                        }
                        for image_url in page_images
                    ],
                ],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "invoice_extraction",
                "strict": False,
                "schema": invoice_schema(),
            }
        },
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
    except httpx.HTTPError as exc:
        raise OpenAIExtractionError(f"OpenAI request failed: {exc}") from exc

    if response.status_code >= 400:
        raise OpenAIExtractionError(_openai_error_message(response))

    output_text = extract_output_text(response.json())
    if not output_text:
        raise OpenAIExtractionError("OpenAI response did not include output text.")
    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise OpenAIExtractionError("OpenAI response was not valid JSON.") from exc


def render_pdf_pages_as_data_urls(pdf_path: Path, max_pages: int = 3) -> List[str]:
    try:
        import fitz
    except ImportError as exc:
        raise OpenAIExtractionError("PyMuPDF missing. Run: pip install -r requirements.txt") from exc

    data_urls: List[str] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page in doc[:max_pages]:
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            encoded = base64.b64encode(pix.tobytes("jpeg", jpg_quality=82)).decode("ascii")
            data_urls.append(f"data:image/jpeg;base64,{encoded}")
    finally:
        doc.close()
    return data_urls


def extract_output_text(payload: Dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: List[str] = []
    for item in payload.get("output", []) or []:
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []) or []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                chunks.append(content["text"])
    return "".join(chunks).strip()


def invoice_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "supplier": {"type": ["string", "null"]},
            "invoice_number": {"type": ["string", "null"]},
            "invoice_date": {"type": ["string", "null"]},
            "currency": {"type": ["string", "null"]},
            "subtotal_ht": {"type": ["number", "null"]},
            "vat_rate": {"type": ["number", "null"]},
            "vat_amount": {"type": ["number", "null"]},
            "total_ttc": {"type": ["number", "null"]},
            "line_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "description": {"type": ["string", "null"]},
                        "quantity": {"type": ["number", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "amount": {"type": ["number", "null"]},
                    },
                    "required": ["description", "quantity", "unit_price", "amount"],
                },
            },
            "confidence": {"type": ["number", "null"]},
            "missing_fields": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "supplier",
            "invoice_number",
            "invoice_date",
            "currency",
            "subtotal_ht",
            "vat_rate",
            "vat_amount",
            "total_ttc",
            "line_items",
            "confidence",
            "missing_fields",
        ],
    }


def _openai_error_message(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except json.JSONDecodeError:
        return f"OpenAI API error {response.status_code}: {response.text[:300]}"
    message = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
    return f"OpenAI API error {response.status_code}: {message or str(payload)[:300]}"
