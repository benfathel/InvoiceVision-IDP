from __future__ import annotations

from pathlib import Path
from typing import Dict

from .export import upsert_result
from .extraction import extract_text_from_pdf
from .models import ProcessingResult
from .parsing import parse_invoice
from .validation import validate_invoice


def process_web_invoice(
    pdf_path: Path,
    file_id: str,
    file_name: str,
    output_dir: Path,
    ocr_language: str = "eng",
) -> Dict[str, object]:
    text, method = extract_text_from_pdf(pdf_path, ocr_language=ocr_language)
    invoice = parse_invoice(text, file_name=file_name, extraction_method=method)
    invoice.file_id = file_id
    invoice.raw_text_chars = len(text)
    anomalies = validate_invoice(invoice)
    result = ProcessingResult(invoice=invoice, anomalies=anomalies)
    summary = upsert_result(result, output_dir)
    payload = result.to_json()
    payload["ocr"] = {
        "method": method,
        "text_chars": len(text),
        "preview": text[:1200],
    }
    payload["exports"] = summary["exports"]
    payload["aggregate"] = {
        "processed": summary["processed"],
        "ok": summary["ok"],
        "review": summary["review"],
    }
    return payload


WEBAPP_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>InvoiceVision IDP</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #16202a;
      --muted: #596879;
      --line: #d7dee7;
      --panel: #ffffff;
      --bg: #f4f7fb;
      --accent: #0b7285;
      --accent-dark: #075968;
      --ok: #1b7f46;
      --review: #a15c00;
      --bad: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    .shell { width: min(1180px, calc(100vw - 32px)); margin: 0 auto; padding: 24px 0 36px; }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 18px; }
    h1 { font-size: 24px; line-height: 1.15; margin: 0; font-weight: 760; }
    .subtle { color: var(--muted); font-size: 13px; }
    .statusbar { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
    .badge { border: 1px solid var(--line); background: #fff; padding: 7px 10px; border-radius: 999px; font-size: 12px; color: var(--muted); white-space: nowrap; }
    .grid { display: grid; grid-template-columns: 340px 1fr; gap: 16px; align-items: start; }
    .panel { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
    .panel-head { padding: 14px 16px; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .panel-head h2 { margin: 0; font-size: 15px; line-height: 1.2; }
    .panel-body { padding: 16px; }
    .drop {
      border: 1px dashed #9bb0c4;
      background: #f8fbff;
      min-height: 156px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: 18px;
    }
    .drop strong { display: block; margin-bottom: 6px; }
    input[type=file] { width: 100%; margin-top: 14px; }
    button {
      width: 100%;
      min-height: 42px;
      margin-top: 14px;
      border: 0;
      border-radius: 6px;
      color: #fff;
      background: var(--accent);
      font-weight: 700;
      cursor: pointer;
    }
    button:hover { background: var(--accent-dark); }
    button:disabled { background: #8aa7b0; cursor: wait; }
    .result-state { font-weight: 760; }
    .ok { color: var(--ok); }
    .review { color: var(--review); }
    .bad { color: var(--bad); }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 10px 12px; vertical-align: top; }
    th { width: 185px; color: var(--muted); font-weight: 700; background: #f9fbfd; }
    td { word-break: break-word; }
    .wide-table th { width: auto; }
    .wide-table td, .wide-table th { white-space: normal; }
    .empty { color: var(--muted); padding: 24px 16px; }
    .split { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 16px; }
    pre {
      margin: 0;
      max-height: 230px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 12px;
      line-height: 1.45;
      color: #23313f;
      background: #f9fbfd;
      padding: 14px;
      border-radius: 6px;
      border: 1px solid var(--line);
    }
    .exports { display: grid; gap: 7px; font-size: 13px; }
    .exports code { color: #203244; }
    @media (max-width: 860px) {
      .grid { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div>
        <h1>InvoiceVision IDP</h1>
        <div class="subtle">Upload a PDF invoice. OpenAI reads page images, then Python validates totals and exports CSV/XLSX.</div>
      </div>
      <div class="statusbar">
        <span class="badge" id="apiStatus">service: checking</span>
        <span class="badge">OpenAI vision extraction</span>
      </div>
    </header>

    <section class="grid">
      <aside class="panel">
        <div class="panel-head"><h2>Upload</h2></div>
        <div class="panel-body">
          <div class="drop" id="drop">
            <div>
              <strong>Drop PDF here</strong>
              <span class="subtle">or choose a file below</span>
            </div>
          </div>
          <input id="file" type="file" accept="application/pdf,.pdf">
          <button id="run" type="button">Upload and Extract</button>
          <p class="subtle" id="message">Ready.</p>
        </div>
      </aside>

      <section class="panel">
        <div class="panel-head">
          <h2>Invoice Table</h2>
          <span class="result-state" id="resultState">No result</span>
        </div>
        <div id="invoiceTable" class="empty">Upload an invoice to see extracted fields.</div>
      </section>
    </section>

    <section class="split">
      <section class="panel">
        <div class="panel-head"><h2>Anomalies</h2></div>
        <div id="anomalyTable" class="empty">No anomalies yet.</div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>OpenAI Run</h2><span class="subtle" id="ocrMeta"></span></div>
        <div class="panel-body"><pre id="ocrPreview">No OpenAI extraction yet.</pre></div>
      </section>
      <section class="panel">
        <div class="panel-head"><h2>Exports</h2></div>
        <div class="panel-body"><div class="exports" id="exports">No exports yet.</div></div>
      </section>
    </section>
  </main>

  <script>
    const fileInput = document.querySelector('#file');
    const runButton = document.querySelector('#run');
    const message = document.querySelector('#message');
    const resultState = document.querySelector('#resultState');
    const invoiceTable = document.querySelector('#invoiceTable');
    const anomalyTable = document.querySelector('#anomalyTable');
    const ocrPreview = document.querySelector('#ocrPreview');
    const ocrMeta = document.querySelector('#ocrMeta');
    const exportsBox = document.querySelector('#exports');
    const apiStatus = document.querySelector('#apiStatus');
    const drop = document.querySelector('#drop');

    fetch('/health')
      .then(r => r.ok ? r.json() : Promise.reject())
      .then(() => { apiStatus.textContent = 'service: online'; })
      .catch(() => { apiStatus.textContent = 'service: offline'; });

    drop.addEventListener('dragover', event => {
      event.preventDefault();
      drop.style.borderColor = '#0b7285';
    });
    drop.addEventListener('dragleave', () => {
      drop.style.borderColor = '#9bb0c4';
    });
    drop.addEventListener('drop', event => {
      event.preventDefault();
      drop.style.borderColor = '#9bb0c4';
      if (event.dataTransfer.files.length) fileInput.files = event.dataTransfer.files;
    });

    runButton.addEventListener('click', async () => {
      const file = fileInput.files[0];
      if (!file) {
        message.textContent = 'Choose a PDF first.';
        return;
      }
      const form = new FormData();
      form.append('invoice', file);
      runButton.disabled = true;
      message.textContent = 'Processing...';
      try {
        const response = await fetch('/web/process', { method: 'POST', body: form });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Processing failed');
        render(payload);
        message.textContent = 'Done.';
      } catch (error) {
        resultState.textContent = 'Error';
        resultState.className = 'result-state bad';
        message.textContent = error.message;
      } finally {
        runButton.disabled = false;
      }
    });

    const demoPayload = {
      status: 'OK',
      invoice: {
        file_name: 'supplier-invoice-mixed-layout.pdf',
        supplier: 'Northline Office Supplies',
        invoice_number: 'INV-2026-0428',
        invoice_date: '2026-04-28',
        subtotal_ht: 1240.00,
        vat_rate: 20.00,
        vat_amount: 248.00,
        total_ttc: 1488.00,
        currency: 'EUR',
        extraction_method: 'openai_vision',
        confidence: 0.96,
        missing_fields: []
      },
      anomalies: [],
      openai: {
        model: 'gpt-5-mini',
        pages_sent: 1
      },
      exports: {
        invoices_csv: 'data/output/invoices.csv',
        invoices_xlsx: 'data/output/invoices.xlsx',
        anomalies_csv: 'data/output/anomalies.csv',
        anomalies_xlsx: 'data/output/anomalies.xlsx',
        summary_json: 'data/output/summary.json'
      }
    };

    if (new URLSearchParams(window.location.search).get('demo') === '1') {
      render(demoPayload);
      message.textContent = 'Demo invoice extracted.';
      apiStatus.textContent = 'service: online';
    }

    function render(payload) {
      const invoice = payload.invoice || {};
      resultState.textContent = payload.status || 'UNKNOWN';
      resultState.className = 'result-state ' + (payload.status === 'OK' ? 'ok' : 'review');
      invoiceTable.innerHTML = keyValueTable([
        ['File', invoice.file_name],
        ['Supplier', invoice.supplier],
        ['Invoice number', invoice.invoice_number],
        ['Invoice date', invoice.invoice_date],
        ['Subtotal HT', invoice.subtotal_ht],
        ['VAT rate', invoice.vat_rate],
        ['VAT amount', invoice.vat_amount],
        ['Total TTC', invoice.total_ttc],
        ['Currency', invoice.currency],
        ['Method', invoice.extraction_method],
        ['Confidence', invoice.confidence],
        ['Missing fields', (invoice.missing_fields || []).join(', ')]
      ]);
      renderAnomalies(payload.anomalies || []);
      const openai = payload.openai || {};
      ocrMeta.textContent = [openai.model, openai.pages_sent ? openai.pages_sent + ' pages' : ''].filter(Boolean).join(' · ');
      ocrPreview.textContent = JSON.stringify(invoice, null, 2);
      renderExports(payload.exports || {});
    }

    function keyValueTable(rows) {
      return '<table><tbody>' + rows.map(([key, value]) =>
        `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value ?? '')}</td></tr>`
      ).join('') + '</tbody></table>';
    }

    function renderAnomalies(rows) {
      if (!rows.length) {
        anomalyTable.innerHTML = '<div class="empty">No anomalies detected.</div>';
        return;
      }
      anomalyTable.innerHTML = '<table class="wide-table"><thead><tr><th>Severity</th><th>Field</th><th>Rule</th><th>Message</th></tr></thead><tbody>' +
        rows.map(row => `<tr><td>${escapeHtml(row.severity)}</td><td>${escapeHtml(row.field)}</td><td>${escapeHtml(row.rule)}</td><td>${escapeHtml(row.message)}</td></tr>`).join('') +
        '</tbody></table>';
    }

    function renderExports(exports) {
      const entries = Object.entries(exports);
      exportsBox.innerHTML = entries.length
        ? entries.map(([key, value]) => `<div><strong>${escapeHtml(key)}</strong>: <code>${escapeHtml(value)}</code></div>`).join('')
        : 'No exports returned.';
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
      }[char]));
    }
  </script>
</body>
</html>
"""
