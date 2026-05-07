import os
import re
import uuid
from datetime import datetime
from pathlib import Path

from .ai_normalization import normalize_ai_invoice
from .export import upsert_result
from .extraction import extract_text_from_pdf
from .models import ProcessingResult
from .openai_extraction import OpenAIExtractionError, process_openai_invoice
from .processor import process_documents
from .validation import validate_invoice
from .webapp import WEBAPP_HTML, process_web_invoice


def create_app():
    try:
        from fastapi import Body, FastAPI, File, HTTPException, UploadFile
        from fastapi.responses import HTMLResponse, JSONResponse
    except ImportError as exc:
        raise RuntimeError("FastAPI missing. Run: pip install -r requirements.txt") from exc

    app = FastAPI(title="Invoice IDP Service", version="0.1.0")
    project_root = Path(os.getenv("INVOICE_IDP_ROOT", Path.cwd())).resolve()
    input_dir = Path(os.getenv("INVOICE_IDP_INPUT_DIR", project_root / "data" / "input"))
    output_dir = Path(os.getenv("INVOICE_IDP_OUTPUT_DIR", project_root / "data" / "output"))
    ocr_language = os.getenv("INVOICE_IDP_OCR_LANG", "eng")

    @app.get("/health")
    async def health():
        return {"status": "ok", "input_dir": str(input_dir), "output_dir": str(output_dir)}

    @app.get("/", response_class=HTMLResponse)
    async def root_app():
        return WEBAPP_HTML

    @app.get("/app", response_class=HTMLResponse)
    async def web_app():
        return WEBAPP_HTML

    @app.post("/web/process")
    async def web_process_invoice(invoice: UploadFile = File(...)):
        file_id, file_name, destination = await _save_upload(invoice, input_dir)
        try:
            payload = process_openai_invoice(
                destination,
                file_id=file_id,
                file_name=file_name,
                output_dir=output_dir,
            )
        except OpenAIExtractionError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return JSONResponse(payload)

    @app.post("/web/process-local")
    async def web_process_invoice_local(invoice: UploadFile = File(...)):
        file_id, file_name, destination = await _save_upload(invoice, input_dir)
        payload = process_web_invoice(
            destination,
            file_id=file_id,
            file_name=file_name,
            output_dir=output_dir,
            ocr_language=ocr_language,
        )
        return JSONResponse(payload)

    @app.post("/ocr")
    async def ocr_invoice(invoice: UploadFile = File(...)):
        file_id, file_name, destination = await _save_upload(invoice, input_dir)
        text, method = extract_text_from_pdf(destination, ocr_language=ocr_language)
        return {
            "file_id": file_id,
            "file_name": file_name,
            "text": text,
            "extraction_method": method,
            "text_chars": len(text),
        }

    @app.post("/validate-export")
    async def validate_export(payload: dict = Body(...)):
        file_id = str(payload.get("file_id") or "")
        file_name = str(payload.get("file_name") or "invoice.pdf")
        extracted_invoice = payload.get("extracted_invoice") or payload.get("invoice") or payload
        invoice_data = normalize_ai_invoice(extracted_invoice, file_name=file_name, file_id=file_id)
        anomalies = validate_invoice(invoice_data)
        result = ProcessingResult(invoice=invoice_data, anomalies=anomalies)
        summary = upsert_result(result, output_dir)
        response = result.to_json()
        response["exports"] = summary["exports"]
        response["aggregate"] = {
            "processed": summary["processed"],
            "ok": summary["ok"],
            "review": summary["review"],
        }
        return JSONResponse(response)

    @app.post("/process")
    async def process_invoice(invoice: UploadFile = File(...)):
        _, _, destination = await _save_upload(invoice, input_dir)
        summary = process_documents(destination, output_dir=output_dir, ocr_language=ocr_language)
        return JSONResponse(summary)

    return app


async def _save_upload(invoice, input_dir: Path):
    from fastapi import HTTPException

    if not invoice.filename or not invoice.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload field 'invoice' must be a PDF file")

    input_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(invoice.filename)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    file_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
    destination = input_dir / f"{file_id}_{safe_name}"
    content = await invoice.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty")
    destination.write_bytes(content)
    return file_id, safe_name, destination


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("._")
    return cleaned or "invoice.pdf"
