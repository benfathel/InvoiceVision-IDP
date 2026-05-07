from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional, Sequence

from .demo import generate_demo_pdfs
from .processor import process_documents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Invoice IDP OCR extraction and anomaly reporting")
    subparsers = parser.add_subparsers(dest="command", required=True)

    process = subparsers.add_parser("process", help="Process one PDF file or a directory of PDFs")
    process.add_argument("--input", required=True, help="PDF file or directory")
    process.add_argument("--output-dir", default="data/output", help="Export directory")
    process.add_argument("--ocr-lang", default="eng", help="Tesseract language, e.g. eng or fra+eng")
    process.add_argument("--force-ocr", action="store_true", help="Force OCR even when PDF text exists")

    demo = subparsers.add_parser("generate-demo", help="Generate demo PDF invoices")
    demo.add_argument("--output-dir", default="data/input", help="Demo PDF directory")

    serve = subparsers.add_parser("serve", help="Start local HTTP service for n8n Docker")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8010)
    serve.add_argument("--reload", action="store_true")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "generate-demo":
        created = generate_demo_pdfs(Path(args.output_dir))
        print(json.dumps({"created": [str(path) for path in created]}, indent=2))
        return 0

    if args.command == "process":
        summary = process_documents(
            input_path=args.input,
            output_dir=args.output_dir,
            ocr_language=args.ocr_lang,
            force_ocr=args.force_ocr,
        )
        print(json.dumps(summary, indent=2))
        return 0

    if args.command == "serve":
        try:
            import uvicorn
        except ImportError as exc:
            raise RuntimeError("uvicorn missing. Run: pip install -r requirements.txt") from exc
        uvicorn.run("invoice_idp.service:create_app", factory=True, host=args.host, port=args.port, reload=args.reload)
        return 0

    parser.error("Unknown command")
    return 2
