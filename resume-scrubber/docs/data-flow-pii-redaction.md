# Data Flow: PII Redaction Pipeline

This document traces the complete data flow for the "Remove Images" workflow — from user input to cleaned output document.

## Overview

```
┌──────────┐     POST /remove-images      ┌───────────┐
│  React   │ ───────────────────────────▶  │  Flask    │
│  SPA     │                               │  app.py   │
│          │  ◀─────────────────────────── │           │
└──────────┘   clean_<filename>.docx       └───────────┘
```

## Detailed Flow

### 1. User Input (Frontend)

The user provides:
- **Name** (text)
- **Job Title** (text)
- **Department** (text)
- **Responsibilities** (rich text via React Quill — produces HTML)
- **Resume file** (`.docx`)

The frontend sends a `multipart/form-data` POST to `/remove-images`.

### 2. Request Handling (`app.py`)

```
POST /remove-images
│
├─ Extract form fields: name, jobTitle, department, responsibilities
├─ Read uploaded .docx file bytes
│
├─ Call clean_resume.process_docx(docx_bytes)
│   │
│   ├─ Parse document.xml via lxml
│   │
│   ├─ _strip_images(body)
│   │   ├─ Find all <w:drawing> elements
│   │   │   └─ Remove if no text content inside
│   │   └─ Find all <w:pict> elements
│   │       └─ Preserve text in <w:txbxContent>, remove image wrapper
│   │
│   ├─ _scrub_paragraphs(body)
│   │   │
│   │   └─ For each <w:p> paragraph:
│   │       ├─ Concatenate text from all <w:t> runs
│   │       ├─ _find_pii_spans(text)
│   │       │   ├─ Phone regex → digit count validation (7-15 digits)
│   │       │   ├─ Email regex
│   │       │   └─ URL regex
│   │       ├─ address_identifier.is_address_line(text)
│   │       │   ├─ Postal code detection (UK, US, CA, NL, international)
│   │       │   ├─ Street type detection (post-suffix, pre-prefix, fused)
│   │       │   ├─ House number detection
│   │       │   └─ Score aggregation → threshold comparison
│   │       │
│   │       └─ _redact_spans_in_runs(paragraph, spans)
│   │           ├─ Map character offsets to <w:r> run elements
│   │           ├─ Replace matched text with "[redacted]"
│   │           └─ Handle spans that cross run boundaries
│   │
│   ├─ _unwrap_hyperlinks(body)
│   │   ├─ Find all <w:hyperlink> elements
│   │   ├─ Extract display text from child runs
│   │   ├─ Prefix with "[redacted]"
│   │   └─ Replace hyperlink element with plain text runs
│   │
│   ├─ _scrub_metadata_xml(docx_zip)
│   │   ├─ Parse docProps/core.xml
│   │   │   └─ Clear: creator, lastModifiedBy, subject, title, keywords, description
│   │   └─ Parse docProps/app.xml
│   │       └─ Clear: Manager, Company
│   │
│   └─ Return cleaned BytesIO (.docx)
│
├─ _prepend_user_info(cleaned_docx, name, title, dept, responsibilities)
│   └─ Insert metadata paragraphs at document start
│
└─ Return response
    ├─ Content-Type: application/octet-stream
    ├─ Content-Disposition: attachment; filename=clean_<original>.docx
    └─ Body: cleaned .docx bytes
```

### 3. Download (Frontend)

The frontend receives the binary response, creates a Blob URL, and triggers a download of `clean_<filename>.docx`.

A warning dialog reminds the user to manually review the document for any remaining PII.

## PII Detection Details

### Phone Number Detection

```
Input:  "+1 (555) 123-4567 ext. 890"
         ├─ Regex match: full string
         ├─ Extract digits: 15551234567890
         ├─ Digit count: 13 (7 ≤ 13 ≤ 15 ✓)
         └─ Result: REDACTED

Input:  "2016"
         ├─ Regex match: "2016"
         ├─ Extract digits: 2016
         ├─ Digit count: 4 (4 < 7 ✗)
         └─ Result: NOT redacted (year, not a phone)
```

### Address Detection Scoring

```
Input:  "123 Main Street, Springfield, IL 62704"
         ├─ Postal code: "62704" → US 5-digit ✓ (+3 points)
         ├─ House number: "123" ✓ (+1 point)
         ├─ Street type: "Street" → English post-suffix ✓ (+2 points)
         ├─ Total score: 6 (threshold: 3)
         └─ Result: Address line removed

Input:  "Managed 5 projects in 2023"
         ├─ Postal code: none
         ├─ House number: "5" (weak signal)
         ├─ Street type: none
         ├─ Total score: 1 (below threshold)
         └─ Result: NOT an address
```
