# ADR-002: OOXML Direct Manipulation over python-docx


## Context

The application needs to:
1. Extract content from a source `.docx` file (resume)
2. Inject that content into a target `.docx` file (template)
3. Preserve paragraph styles, numbering, bullet lists, and text formatting (bold, italic, underline)
4. Remove images, hyperlinks, and style references that would break in the target document

The `python-docx` library provides high-level abstractions for `.docx` manipulation but does not support several critical operations:
- Deep-copying `<w:p>` elements between documents
- Merging `numbering.xml` definitions
- Manipulating structured document tags (`<w:sdt>`)
- Removing specific OOXML elements while preserving siblings

## Decision

Perform direct OOXML/XML manipulation using **lxml** for all template population and PII redaction operations. Use `python-docx` only for high-level document I/O (opening/saving `.docx` files).

Key implementation details:
- `SectionXmlParser` deep-copies `<w:p>` (paragraph) elements from the source and sanitizes them for the target context
- `DocxPopulator` merges numbering definitions (`<w:abstractNum>`, `<w:num>`) from source into template's `numbering.xml`
- `clean_resume.py` directly removes `<w:drawing>`, `<w:pict>`, and `<w:hyperlink>` elements via lxml tree operations
- OOXML namespace handling uses a centralized namespace map (`_NS`) for `w:`, `r:`, `wp:`, etc.

## Consequences

### Positive
- Full control over the OOXML tree — no abstraction leakage
- Can enforce OOXML invariants (no empty `<w:sdtContent/>`, no `<w:tc>` without `<w:p>`) that python-docx does not validate
- Numbering definition merging ensures bullet/list styles transfer correctly between documents
- Images and hyperlinks can be surgically removed without affecting surrounding text

### Negative
- Higher complexity: developers must understand OOXML schema (ISO/IEC 29500)
- No abstraction safety net — malformed XML produces corrupt documents
- More verbose code than python-docx equivalents for simple operations
- OOXML invariant enforcement (`_enforce_ooxml_invariants()`) is necessary to prevent Word from rejecting output

### Alternatives Considered
- **python-docx only**: Insufficient for cross-document element injection and numbering merge
- **docxtpl (Jinja templates)**: Does not support XML-level manipulation; limited to text substitution
- **pandoc**: Lossy format conversion; no fine-grained control over OOXML elements
