# ADR-004: Pair-Based Text-XML Architecture


## Context

The template population pipeline requires two different views of the same resume content:

1. **Plain text** — for NLP processing (NER entity recognition, header keyword matching, section classification)
2. **OOXML elements** — for template injection (preserving formatting, bullet numbering, font styles)

Extracting text and XML independently risks misalignment: section boundaries determined from text parsing may not correspond to the correct XML elements, leading to content duplication or omission.

## Decision

`TextExtractor.extract_pairs()` returns a list of `(cleaned_text, <w:p> element)` tuples, where each tuple represents a single paragraph in document order. All downstream modules operate on these pairs:

- `ModelSectionParser.find_sections()` reads the text component for classification, groups pairs by section
- `SectionXmlParser.build_for_section()` reads the XML component from the classified pairs for template injection
- Deduplication (merged table cells producing identical consecutive lines) operates on pairs, removing both text and XML together

## Consequences

### Positive
- **Guaranteed alignment**: Text and XML always correspond to the same paragraph — no index mismatches
- **Single extraction pass**: One traversal of the document tree produces both views
- **Composable pipeline**: Each stage receives pairs, filters/transforms them, and passes them downstream
- **Safe deep-copy**: XML elements are deep-copied before injection, preventing reference cycles between source and target documents

### Negative
- Memory usage is higher than text-only extraction (XML elements kept in memory alongside text)
- All downstream modules must accept the pair format, coupling them to `TextExtractor`'s output schema
- Unicode normalization (tabs → spaces, smart quotes → ASCII) is applied during extraction, so the XML text content may diverge from the normalized text string

### Alternatives Considered
- **Separate text and XML extraction**: Simpler individual implementations but prone to alignment bugs when section boundaries are determined from text and applied to XML
- **Index-based mapping**: Extract text and XML separately, then map by paragraph index — fragile if extraction logic differs (e.g., one skips empty paragraphs and the other does not)
- **Re-parse XML from text**: Extract text only, then re-parse the document to find matching XML — O(n²) and unreliable for duplicate paragraphs
