# InvoiceVision IDP

InvoiceVision IDP is a local n8n + OpenAI + Python tool for extracting, validating, and exporting invoice data from variable-format PDF invoices.

n8n orchestre le workflow: upload PDF, extraction LLM structuree, validation metier, export Excel/CSV. Python reste en support pour le rendu PDF, les controles deterministes et les exports.

Note: ce projet n'utilise pas UiPath. Si une variante UiPath est ajoutee plus tard, elle devra etre marquee clairement `UiPath Community project`.

## Architecture

- n8n Docker existant: `n8n-n8n` sur `http://localhost:5678`.
- Webhook n8n: upload multipart du champ `invoice`.
- Python local: `http://host.docker.internal:8010` depuis le container n8n.
- OpenAI dans n8n: noeud `OpenAI Chat Model`, modele `gpt-5-mini`.
- Extraction structuree: noeud n8n `Information Extractor`.
- Validation Python: fournisseur, numero facture, date, Total HT, TVA, Total TTC, confiance LLM.
- Exports: `invoices.csv`, `invoices.xlsx`, `anomalies.csv`, `anomalies.xlsx`, `summary.json`.

## Installation Python

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Verifier Tesseract:

```bash
tesseract --version
tesseract --list-langs
```

Par defaut le projet utilise `eng`. Installer le pack `fra` pour `INVOICE_IDP_OCR_LANG=fra+eng`.

## Service Python

Demarrer le service local:

```bash
PYTHONPATH=src python -m invoice_idp serve --host 0.0.0.0 --port 8010
```

Endpoints:

- `GET /health`
- `GET /app`: application web locale.
- `POST /web/process`: extraction OpenAI Vision only, validation et export.
- `POST /web/process-local`: legacy local OCR/parser pour comparaison.
- `POST /ocr`: champ multipart `invoice`, retourne `file_id`, `file_name`, `text`, `extraction_method`, `text_chars`.
- `POST /validate-export`: recoit le JSON extrait par le LLM, valide et met a jour les exports.
- `POST /process`: legacy, pipeline Python regex-only garde pour compatibilite.

## Webapp OpenAI only

Configurer la cle OpenAI dans le shell qui lance le service:

```bash
export OPENAI_API_KEY="sk-..."
export OPENAI_INVOICE_MODEL="gpt-5-mini"
PYTHONPATH=src python -m invoice_idp serve --host 0.0.0.0 --port 8010
```

Ouvrir:

```text
http://localhost:8010/app
```

Le PDF est rendu en images puis envoye a OpenAI via Responses API avec image input et JSON structure. Aucun OCR Tesseract n'est utilise pour `/web/process`.

## Workflow n8n AI

Workflow source:

```text
n8n/workflows/invoice_idp_upload_workflow.json
```

Workflow dans n8n:

```text
Pxkz5MHhdqViFi2v
```

Flux:

```text
Webhook PDF -> HTTP /ocr -> Information Extractor -> OpenAI Chat Model -> HTTP /validate-export -> response JSON
```

Avant activation:

1. Ouvrir n8n sur `http://localhost:5678`.
2. Ouvrir le workflow `Invoice IDP - AI PDF Upload`.
3. Configurer un credential OpenAI sur le noeud `OpenAI Invoice Model`.
4. Demarrer le service Python local.
5. Tester avec un PDF dans le champ multipart `invoice`.
6. Activer seulement apres test.

URL active apres activation:

```text
http://localhost:5678/webhook/invoice-upload
```

## Demo CLI

Generer des factures PDF demo:

```bash
PYTHONPATH=src python -m invoice_idp generate-demo --output-dir data/input
```

Pipeline legacy Python seul:

```bash
PYTHONPATH=src python -m invoice_idp process --input data/input --output-dir data/output
```

## Tests

```bash
PYTHONPATH=src python -m unittest discover -s tests
```

## Resultats attendus

- Facture valide: statut `OK`.
- TVA incorrecte: anomalie `vat_rate_match`.
- Total incorrect: anomalie `total_match`.
- Champ manquant: anomalie `required_field`.
- Confiance LLM faible: anomalie `low_confidence`.
- Validation humaine: ouvrir `data/output/anomalies.xlsx`.
