from decimal import Decimal
import unittest

from invoice_idp.parsing import parse_invoice
from invoice_idp.validation import validate_invoice


VALID_TEXT = """
Invoice
Supplier: Acme Office SARL
Invoice No: FAC-2026-001
Date: 2026-04-30
Subtotal HT: 1000.00 EUR
TVA 20%: 200.00 EUR
Total TTC: 1200.00 EUR
"""


class ParsingValidationTests(unittest.TestCase):
    def test_parse_invoice_fields(self):
        invoice = parse_invoice(VALID_TEXT, "valid.pdf")

        self.assertEqual(invoice.supplier, "Acme Office SARL")
        self.assertEqual(invoice.invoice_number, "FAC-2026-001")
        self.assertEqual(invoice.invoice_date.isoformat(), "2026-04-30")
        self.assertEqual(invoice.subtotal_ht, Decimal("1000.00"))
        self.assertEqual(invoice.vat_rate, Decimal("20"))
        self.assertEqual(invoice.vat_amount, Decimal("200.00"))
        self.assertEqual(invoice.total_ttc, Decimal("1200.00"))

    def test_valid_invoice_has_no_anomaly(self):
        invoice = parse_invoice(VALID_TEXT, "valid.pdf")
        self.assertEqual(validate_invoice(invoice), [])

    def test_vat_mismatch_is_reported(self):
        text = VALID_TEXT.replace("TVA 20%: 200.00", "TVA 20%: 180.00").replace("1200.00", "1180.00")
        invoice = parse_invoice(text, "bad-vat.pdf")
        rules = {item.rule for item in validate_invoice(invoice)}
        self.assertIn("vat_rate_match", rules)

    def test_total_mismatch_is_reported(self):
        text = VALID_TEXT.replace("Total TTC: 1200.00", "Total TTC: 900.00")
        invoice = parse_invoice(text, "bad-total.pdf")
        rules = {item.rule for item in validate_invoice(invoice)}
        self.assertIn("total_match", rules)

    def test_missing_supplier_is_reported(self):
        text = VALID_TEXT.replace("Supplier: Acme Office SARL\n", "")
        invoice = parse_invoice(text, "missing-supplier.pdf")
        rules = {item.rule for item in validate_invoice(invoice)}
        self.assertIn("required_field", rules)


if __name__ == "__main__":
    unittest.main()
