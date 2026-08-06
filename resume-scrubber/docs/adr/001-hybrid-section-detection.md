# ADR-001: Hybrid ML + Heuristic Section Detection


## Context

Resumes vary widely in structure. Some have clear section headers ("EDUCATION", "WORK EXPERIENCE"), while others use non-standard names ("Academic Background", "Professional History") or omit headers entirely, relying on formatting cues like bold text or horizontal rules.

A purely header-based parser fails on resumes without standard headers. A purely ML-based approach (NER entity voting) misclassifies paragraphs when entities appear in unexpected sections (e.g., a company name mentioned under education as an internship sponsor).

## Decision

Use a **hybrid multi-pass approach** in `ModelSectionParser`:

1. **Header pass (heuristic):** Scan each paragraph against curated keyword lists for education and experience headers. When found, establish hard zone boundaries — all subsequent paragraphs belong to that zone until the next header.

2. **Model pass (ML):** Run every paragraph through the spaCy NER model via `nlp.pipe()`. Count entity votes:
   - Education entities: `COLLEGE_NAME`, `DEGREE`, `GRADUATION_YEAR`
   - Experience entities: `COMPANIES_WORKED_AT`, `YEARS_OF_EXPERIENCE`

3. **Resolution:** Headers always win. The model fills in paragraphs that fall outside any header-defined zone for sections that lack a header.

4. **Block propagation:** When the model detects an "entry line" (a paragraph with entities for a section that has no header), all subsequent paragraphs are consumed into that section until:
   - A header boundary is encountered
   - The model votes for a different section on a subsequent line (indicating a new entry started)
   - The model votes for the same section again (propagation continues with the new entry)

   This ensures that description/bullet lines following an entry are captured even though they contain no entities themselves. Propagation overrides any zone-based assignment from step 3 — so experience bullets that happen to sit inside an education header zone are correctly reassigned.

5. **Contiguity smoothing:** Lone unassigned gaps between two paragraphs of the same section adopt that section.

## Consequences

### Positive
- Handles resumes with missing or non-standard headers better than header-only
- Block propagation captures full resume entries (title line + description bullets), not just the entity-bearing first line
- Headers provide reliable boundaries where they exist, preventing entity-level misclassification
- Propagation can override zone-based assignments, correctly recovering content that appears inside an unrelated header zone
- Graceful degradation: if the spaCy model fails to load, falls back to header-only (`use_model=False`)

### Negative
- Two code paths increase maintenance burden
- The keyword lists require curation for new languages or resume styles
- NER model training data must be kept current with evolving resume formats

### Alternatives Considered
- **Header-only parser** (`SectionParser`): Still available as fallback; insufficient for headerless resumes
- **Pure ML segmentation**: Too sensitive to entity leakage across sections; no hard boundary enforcement
- **LLM-based extraction**: Higher latency and cost; unnecessary for structured section detection
