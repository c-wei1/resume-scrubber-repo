# Resume Scrubber

A document processing application that sanitizes resumes by redacting PII (personally identifiable information) and optionally populates a standardized CV template using ML-driven section extraction. Designed for regulated environments requiring GVault-ready (Veeva Vault) CV documents.

## Features

- **PII Redaction** — Strips emails, phone numbers, URLs (including bare domains like `linkedin.com`), city/state locations, home addresses, and images from `.docx` resumes while preserving formatting
- **Experience Entry Insertion** — Inserts Gilead Sciences Inc. role details (title, department, date, responsibilities) into the experience section with font matching and right-aligned dates. Uses a 3-step fallback: experience header detection → NER model → top of document
- **Template Population** — Extracts education and experience sections from a source resume using a hybrid approach (header heuristics + spaCy NER model with block propagation) and injects them into a standardized template (FRM-11110)
- **Rich Text Support** — User-provided responsibilities rendered with bullets, bold, italic, and underline formatting via a Quill editor
- **Multilingual Address Detection** — Identifies addresses across English, Germanic, Romance, Scandinavian, and other formats using multi-signal scoring
- **Metadata Scrubbing** — Removes PII from document properties (author, last modified by, subject, etc.)

## Architecture

```
┌─────────────────────────────┐
│   React SPA (Vite + Quill)  │
│   frontend/src/App.jsx      │
└────────────┬────────────────┘
             │  POST /remove-images
             │  POST /populate-template
             ▼
┌─────────────────────────────┐
│   Flask API (Gunicorn)      │
│   backend/app.py            │
├─────────────────────────────┤
│ Workflow A: PII Redaction   │
│   clean_resume.py           │
│   address_identifier.py     │
├─────────────────────────────┤
│ Workflow B: Template Pop.   │
│   populate_with_model.py    │
│   model_section_parser.py   │
│   parser_get_text.py        │
│   parser_get_section_xml.py │
│   populate_template.py      │
│   html_to_docx.py           │
├─────────────────────────────┤
│ ML Models                   │
│   resume_ner_model/ (spaCy) │
│   *.pkl (Naive Bayes)       │
└─────────────────────────────┘
```

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite 5, React Quill 2.0 |
| Backend | Python, Flask, Flask-CORS |
| Server | Gunicorn (120s timeout) |
| NLP/ML | spaCy 3.8, scikit-learn (Naive Bayes) |
| Document parsing | lxml, python-docx |
| Deployment | Google Cloud App Engine (`app.yaml`) |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download the spaCy base model (if not bundled)
python -m spacy download en_core_web_md

# Run the development server
python -m flask --app backend.app run --port 5000
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server (proxies API calls to localhost:5000)
npm run dev
```

### Production Build

```bash
# Build the frontend into backend/static/
cd frontend && npm run build

# Serve with Gunicorn
gunicorn backend.app:app --bind 0.0.0.0:8000 --timeout 120
```

## API Endpoints

### `POST /remove-images`

Accepts a `.docx` file with user metadata. Returns a cleaned copy with PII redacted and images removed.

**Form fields:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | `.docx` resume |
| `name` | string | Yes | Employee name |
| `jobTitle` | string | Yes | Job title |
| `department` | string | Yes | Department |
| `responsibilities` | string | Yes | Current responsibilities (Quill HTML) |

**Response:** `application/octet-stream` — cleaned `.docx` file

### `POST /populate-template`

Accepts a `.docx` resume. Extracts education/experience via ML, populates the company CV template, and returns the result.

**Form fields:** Same as `/remove-images`

**Response:** `application/octet-stream` — populated template `.docx` file

## Project Structure

```
├── app.yaml                    # GCP App Engine deployment config
├── requirements.txt            # Python dependencies
├── backend/
│   ├── app.py                  # Flask routes and Quill→OOXML conversion
│   ├── clean_resume.py         # PII redaction engine
│   ├── address_identifier.py   # Multilingual address detection
│   ├── html_to_docx.py         # Quill HTML → paragraph structure parser
│   ├── populate_with_model.py  # End-to-end model-driven template population
│   ├── model_section_parser.py # Hybrid ML + header section segmentation
│   ├── parser_get_text.py      # .docx text + XML pair extraction
│   ├── parser_get_section.py   # Header-only section detection (fallback)
│   ├── parser_get_section_xml.py # XML sanitization for template injection
│   ├── populate_template.py    # Template injection engine (OOXML)
│   ├── parser_get_experience.py # Structured experience parsing (NB classifier)
│   ├── parser_get_education.py # Education entry parsing (deprecated)
│   ├── parser.py               # CLI entry point for testing
│   ├── nbc.py                  # Naive Bayes model training script
│   ├── resume_ner_model/       # Trained spaCy NER model
│   └── static/                 # Built frontend (served by Flask)
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx             # Main SPA component
        ├── main.jsx            # React entry point
        └── quill-custom.css    # Editor styling
```

## Documentation

See the [docs/](docs/) directory for architectural decision records and detailed data flow documentation:

- [ADR-001: Hybrid ML + Heuristic Section Detection](docs/adr/001-hybrid-section-detection.md)
- [ADR-002: OOXML Direct Manipulation](docs/adr/002-ooxml-direct-manipulation.md)
- [ADR-003: PII Redaction Strategy](docs/adr/003-pii-redaction-strategy.md)
- [ADR-004: Pair-Based Text-XML Architecture](docs/adr/004-pair-based-architecture.md)
- [Data Flow: PII Redaction Pipeline](docs/data-flow-pii-redaction.md)
- [Data Flow: Template Population Pipeline](docs/data-flow-template-population.md)
