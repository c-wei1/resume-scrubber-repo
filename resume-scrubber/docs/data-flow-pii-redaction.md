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
├─ Extract form fields: name, jobTitle, department, startDate, responsibilities
├─ Read uploaded .docx file bytes
│
├─ If user provided title/department/startDate/responsibilities:
│   └─ _insert_experience_entry(docx_bytes, title, dept, startDate, responsibilities)
│       ├─ Detect experience section (3-step fallback):
│       │   ├─ Step 1: Scan all paragraphs for experience header keyword
│       │   ├─ Step 2: NER ModelSectionParser → text-match first experience paragraph
│       │   └─ Step 3: Last resort → insert at top of document body
│       ├─ Detect font name + size from experience section (python-docx, capped at 12pt)
│       ├─ Build entry paragraphs:
│       │   ├─ "Current Responsibilities" (bold + underlined)
│       │   ├─ "Title, Department, Gilead Sciences Inc." with right-aligned date
│       │   └─ Quill HTML → formatted bullet paragraphs
│       └─ Insert right after experience header within its parent container
│
├─ Call clean_resume.process_docx(docx_bytes)
│   │
│   ├─ _process_tree(tree)  [for document.xml, headers, footers]
│   │   │
│   │   ├─ _unwrap_hyperlinks(tree)
│   │   │   ├─ Find all <w:hyperlink> elements
│   │   │   ├─ Blank display text
│   │   │   └─ Unwrap hyperlink, move child runs to parent
│   │   │
│   │   ├─ _scrub_paragraphs(tree)
│   │   │   │
│   │   │   └─ For each <w:p> paragraph:
│   │   │       ├─ Concatenate text from all <w:t> runs
│   │   │       ├─ _strip_pii_for_address_check(text)
│   │   │       │   └─ Remove phone/email/URL patterns (prevents phone digits
│   │   │       │      from inflating address score)
│   │   │       ├─ address_identifier.is_address_line(stripped_text)
│   │   │       │   ├─ Postal code detection (UK, US, CA, NL, international)
│   │   │       │   ├─ Street type detection (post-suffix, pre-prefix, fused)
│   │   │       │   ├─ House number detection
│   │   │       │   └─ Score aggregation → threshold (5) comparison
│   │   │       │   └─ If address → remove all runs in paragraph
│   │   │       │
│   │   │       ├─ _find_pii_spans(text)
│   │   │       │   ├─ Phone regex → digit-count validation (7–15 digits)
│   │   │       │   ├─ Email regex
│   │   │       │   ├─ URL regex (incl. bare domains: linkedin.com, etc.)
│   │   │       │   └─ City, STATE pattern (e.g., "San Francisco, CA")
│   │   │       │
│   │   │       └─ _redact_spans_in_runs(paragraph, spans)
│   │   │           ├─ Map character offsets to <w:r> run elements
│   │   │           ├─ Replace matched text with empty string
│   │   │           └─ Handle spans that cross run boundaries
│   │   │
│   │   ├─ _clean_floating_pipes(tree)
│   │   │   └─ Remove orphaned "|" separators after PII removal
│   │   │
│   │   └─ _strip_images(tree)
│   │       ├─ Find all <w:drawing> and <w:pict> elements
│   │       └─ Remove if no text content inside; preserve text boxes
│   │
│   ├─ _scrub_metadata_xml(docProps/*.xml)
│   │   └─ Clear: creator, lastModifiedBy, subject, title, keywords, description
│   │
│   ├─ _strip_rels(document.xml.rels, header/footer rels)
│   │   └─ Remove image and hyperlink relationship entries
│   │
│   ├─ Delete media files (word/media/*)
│   │
│   └─ Repack and return cleaned BytesIO (.docx)
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
