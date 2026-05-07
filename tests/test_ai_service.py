import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from invoice_idp.openai_extraction import extract_output_text, render_pdf_pages_as_data_urls
from invoice_idp.ai_normalization import normalize_ai_invoice
from invoice_idp.demo import generate_demo_pdfs
from invoice_idp.service import create_app
from invoice_idp.validation import validate_invoice


class AiNormalizationTests(unittest.TestCase):
    def test_normalizes_ai_payload_and_validates(self):
        invoice = normalize_ai_invoice(
            {
                "output": {
                    "supplier": "Variable Layout Ltd",
                    "invoice_number": "INV-42",
                    "invoice_date": "30/04/2026",
                    "currency": "eur",
                    "subtotal_ht": "1 000,00 EUR",
                    "vat_rate": "20%",
                    "vat_amount": "200,00",
                    "total_ttc": "1200.00",
                    "line_items": [
                        {
                            "description": "Consulting",
                            "quantity": "2",
                            "unit_price": "500",
                            "amount": "1000",
                        }
                    ],
                    "confidence": 0.92,
                    "missing_fields": [],
                }
            },
            file_name="invoice.pdf",
            file_id="abc",
        )

        self.assertEqual(invoice.supplier, "Variable Layout Ltd")
        self.assertEqual(invoice.invoice_date.isoformat(), "2026-04-30")
        self.assertEqual(invoice.currency, "EUR")
        self.assertEqual(invoice.line_items[0]["amount"], "1000.00")
        self.assertEqual(validate_invoice(invoice), [])


class ServiceEndpointTests(unittest.TestCase):
    def test_webapp_page_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.environ["INVOICE_IDP_INPUT_DIR"] = str(root / "input")
            os.environ["INVOICE_IDP_OUTPUT_DIR"] = str(root / "output")
            client = TestClient(create_app())

            response = client.get("/app")

            self.assertEqual(response.status_code, 200)
            self.assertIn("InvoiceVision IDP", response.text)

    def test_ocr_and_validate_export_endpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "output"
            os.environ["INVOICE_IDP_INPUT_DIR"] = str(input_dir)
            os.environ["INVOICE_IDP_OUTPUT_DIR"] = str(output_dir)
            pdf = generate_demo_pdfs(root / "demo")[0]

            client = TestClient(create_app())
            with pdf.open("rb") as handle:
                ocr_response = client.post(
                    "/ocr",
                    files={"invoice": ("demo.pdf", handle, "application/pdf")},
                )

            self.assertEqual(ocr_response.status_code, 200)
            ocr_payload = ocr_response.json()
            self.assertGreater(ocr_payload["text_chars"], 40)
            self.assertTrue(ocr_payload["file_id"])

            validate_response = client.post(
                "/validate-export",
                json={
                    "file_id": ocr_payload["file_id"],
                    "file_name": ocr_payload["file_name"],
                    "extracted_invoice": {
                        "supplier": "Acme Office SARL",
                        "invoice_number": "FAC-2026-001",
                        "invoice_date": "2026-04-30",
                        "currency": "EUR",
                        "subtotal_ht": 1000,
                        "vat_rate": 20,
                        "vat_amount": 200,
                        "total_ttc": 1200,
                        "line_items": [],
                        "confidence": 0.95,
                        "missing_fields": [],
                    },
                },
            )

            self.assertEqual(validate_response.status_code, 200)
            payload = validate_response.json()
            self.assertEqual(payload["status"], "OK")
            self.assertTrue((output_dir / "invoices.csv").exists())
            self.assertTrue((output_dir / "anomalies.xlsx").exists())

    def test_web_process_requires_openai_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "output"
            os.environ["INVOICE_IDP_INPUT_DIR"] = str(input_dir)
            os.environ["INVOICE_IDP_OUTPUT_DIR"] = str(output_dir)
            os.environ.pop("OPENAI_API_KEY", None)
            pdf = generate_demo_pdfs(root / "demo")[0]

            client = TestClient(create_app())
            with pdf.open("rb") as handle:
                response = client.post(
                    "/web/process",
                    files={"invoice": ("demo.pdf", handle, "application/pdf")},
                )

            self.assertEqual(response.status_code, 502)
            self.assertIn("OPENAI_API_KEY", response.json()["detail"])

    def test_web_process_local_endpoint_returns_table_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_dir = root / "input"
            output_dir = root / "output"
            os.environ["INVOICE_IDP_INPUT_DIR"] = str(input_dir)
            os.environ["INVOICE_IDP_OUTPUT_DIR"] = str(output_dir)
            pdf = generate_demo_pdfs(root / "demo")[0]

            client = TestClient(create_app())
            with pdf.open("rb") as handle:
                response = client.post(
                    "/web/process-local",
                    files={"invoice": ("demo.pdf", handle, "application/pdf")},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["status"], "OK")
            self.assertEqual(payload["invoice"]["invoice_number"], "FAC-2026-001")
            self.assertIn("ocr", payload)
            self.assertTrue((output_dir / "invoices.xlsx").exists())

    def test_pdf_pages_render_for_openai_vision(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = generate_demo_pdfs(Path(tmp) / "demo")[0]
            images = render_pdf_pages_as_data_urls(pdf)

            self.assertTrue(images)
            self.assertTrue(images[0].startswith("data:image/jpeg;base64,"))

    def test_extract_output_text_from_responses_payload(self):
        payload = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "{\"supplier\":\"Acme\"}"}
                    ],
                }
            ]
        }

        self.assertEqual(extract_output_text(payload), "{\"supplier\":\"Acme\"}")


if __name__ == "__main__":
    unittest.main()
