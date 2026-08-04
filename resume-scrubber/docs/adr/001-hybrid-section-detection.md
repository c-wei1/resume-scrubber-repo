# ADR-001: Hybrid ML + Heuristic Section Detection


## Context

Resumes vary widely in structure. Some have clear section headers ("EDUCATION", "WORK EXPERIENCE"), while others use non-standard names ("Academic Background", "Professional History") or omit headers entirely, relying on formatting cues like bold text or horizontal rules.

A purely header-based parser fails on resumes without standard headers. A purely ML-based approach (NER entity voting) misclassifies paragraphs when entities appear in unexpected sections (e.g., a company name mentioned under education as an internship sponsor).

## Decision

Use a **hybrid two-pass approach** in `ModelSectionParser`:

1. **Header pass (heuristic):** Scan each paragraph against curated keyword lists for education and experience headers. When found, establish hard zone boundaries — all subsequent paragraphs belong to that zone until the next header.

2. **Model pass (ML):** Run every paragraph through the spaCy NER model via `nlp.pipe()`. Count entity votes:
   - Education entities: `COLLEGE_NAME`, `DEGREE`, `GRADUATION_YEAR`
   - Experience entities: `COMPANIES_WORKED_AT`, `YEARS_OF_EXPERIENCE`

3. **Resolution:** Headers always win. The model fills in paragraphs that fall outside any header-defined zone. Paragraphs in "other" zones (e.g., SKILLS, SUMMARY) are never assigned to education or experience.

## Consequences

### Positive
- Handles resumes with missing or non-standard headers better than header-only
- Headers provide reliable boundaries where they exist, preventing entity-level misclassification
- Graceful degradation: if the spaCy model fails to load, falls back to header-only (`use_model=False`)

### Negative
- Two code paths increase maintenance burden
- The keyword lists require curation for new languages or resume styles
- NER model training data must be kept current with evolving resume formats

### Alternatives Considered
- **Header-only parser** (`SectionParser`): Still available as fallback; insufficient for headerless resumes
- **Pure ML segmentation**: Too sensitive to entity leakage across sections; no hard boundary enforcement
- **LLM-based extraction**: Higher latency and cost; unnecessary for structured section detection
