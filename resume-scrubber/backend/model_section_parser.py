"""
ModelSectionParser
==================

A drop-in replacement for `SectionParser` that assigns each (text, <w:p>) Pair
to the "education" / "experience" section using a HYBRID of:

    1. Header detection   — the primary, high-precision boundary signal
                            (an explicit "EDUCATION" / "WORK EXPERIENCE" line).
    2. Trained spaCy NER  — a secondary signal: a paragraph that contains
                            COLLEGE_NAME / DEGREE / GRADUATION_YEAR entities
                            votes "education"; COMPANIES_WORKED_AT /
                            YEARS_OF_EXPERIENCE votes "experience".

Why hybrid?  The NER model finds *entities*, not section *boundaries*. Headers
are the reliable boundary cue, so they win when present. The model fills the
gaps — resumes with missing/oddly-named headers, or stray paragraphs that sit
outside any header zone — which is exactly where the old header-only parser
under-segments.

Interface (matches SectionParser so it's a drop-in):
    parser = ModelSectionParser("./resume_ner_model")
    sections = parser.find_sections(pairs)      # {"education": [...], "experience": [...]}
    text     = ModelSectionParser.section_text(sections["education"])

`Pair` is imported from parser_get_section when available; otherwise a
compatible (text, xml) namedtuple fallback is defined so this module can be
imported and unit-tested standalone.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List, Optional

# ── Pair type (reuse yours if present) ────────────────────────────────────────
try:
    from parser_get_section import Pair  # type: ignore
except Exception:  # pragma: no cover - fallback for standalone use/tests
    from collections import namedtuple
    Pair = namedtuple("Pair", ["text", "xml"])


# ── Header vocabulary (kept identical to extract_resume.py) ───────────────────
SECTION_ALIASES = {
    "education": [
        "education", "educational qualifications", "academic", "academics",
        "academic background", "qualifications", "educational background",
    ],
    "experience": [
        "experience", "work experience", "professional experience",
        "employment", "employment history", "work history", "career history",
        "professional background", "relevant experience",
    ],
}
OTHER_HEADERS = [
    "skills", "technical skills", "projects", "summary", "objective",
    "certifications", "achievements", "awards", "publications", "interests",
    "personal details", "contact", "references", "languages", "profile",
    "additional information", "activities", "personality traits",
]

# ── Entity-label → section vote ───────────────────────────────────────────────
EDU_LABELS = {"COLLEGE_NAME", "DEGREE", "GRADUATION_YEAR"}
EXP_LABELS = {"COMPANIES_WORKED_AT", "YEARS_OF_EXPERIENCE"}


def _looks_like_header(line: str) -> Optional[str]:
    """Return 'education' / 'experience' / 'other' if `line` is a header, else None."""
    raw = (line or "").strip().strip(":").strip()
    if not raw or len(raw) > 45:
        return None
    low = raw.lower()
    letters = re.sub(r"[^a-z]", "", low)
    if not letters:
        return None

    def _match(aliases: List[str]) -> bool:
        for a in aliases:
            if low == a or low.startswith(a + " ") or low.startswith(a + ":"):
                return True
            if a in low and len(letters) <= len(a.replace(" ", "")) + 6:
                return True
        return False

    for canonical, aliases in SECTION_ALIASES.items():
        if _match(aliases):
            return canonical
    for h in OTHER_HEADERS:
        if low == h or low.startswith(h + " ") or (
            h in low and len(letters) <= len(h.replace(" ", "")) + 4
        ):
            return "other"
    if raw.isupper():
        for canonical, aliases in SECTION_ALIASES.items():
            if any(a in low for a in aliases):
                return canonical
        if any(h in low for h in OTHER_HEADERS):
            return "other"
    return None


def _ptext(pair) -> str:
    """
    Return the text side of a pair, working for BOTH:
      * Pair namedtuples  -> pair.text
      * plain (text, xml) tuples (what TextExtractor.extract_pairs returns)
                          -> pair[0]
    """
    txt = getattr(pair, "text", None)
    if txt is None and isinstance(pair, (tuple, list)) and len(pair) >= 1:
        txt = pair[0]
    return txt or ""


class ModelSectionParser:
    def __init__(
        self,
        model_path: Optional[str] = None,
        use_model: bool = True,
        include_header_paragraph: bool = False,
    ):
        """
        model_path            : path to the fine-tuned spaCy model dir.
        use_model             : if False, behaves as header-only (safe fallback).
        include_header_paragraph : if True, the "EDUCATION"/"EXPERIENCE" header
                                    line itself is kept in the section's pairs.
                                    Default False (the template supplies headings).
        """
        self.include_header_paragraph = include_header_paragraph
        self.nlp = None
        if use_model and model_path:
            try:
                import spacy
                self.nlp = spacy.load(model_path)
            except Exception as e:  # degrade gracefully to header-only
                print(f"[ModelSectionParser] WARN: could not load model "
                      f"'{model_path}' ({str(e)[:70]}). Falling back to header-only.")
                self.nlp = None

    # ── model votes (batched) ────────────────────────────────────────────────
    def _model_votes(self, texts: List[str]) -> List[Optional[str]]:
        """One vote per paragraph: 'education' / 'experience' / None."""
        if self.nlp is None:
            return [None] * len(texts)
        votes: List[Optional[str]] = []
        for doc in self.nlp.pipe(texts, batch_size=64):
            edu = sum(1 for e in doc.ents if e.label_ in EDU_LABELS)
            exp = sum(1 for e in doc.ents if e.label_ in EXP_LABELS)
            if edu == 0 and exp == 0:
                votes.append(None)
            elif edu >= exp:
                votes.append("education")
            else:
                votes.append("experience")
        return votes

    # ── main API ─────────────────────────────────────────────────────────────
    def find_sections(self, pairs: List[Pair]) -> Dict[str, List[Pair]]:
        """
        Assign every Pair to a section and return
        {"education": [Pair, ...], "experience": [Pair, ...]}.
        """
        texts = [_ptext(p) for p in pairs]
        n = len(pairs)

        # 1) Header pass → hard section zones + mark header lines.
        #    zone[i] is one of: 'education' | 'experience' | 'other' | None
        #    ('other' = inside a recognised non-target header like SKILLS/SUMMARY;
        #     None    = preamble before the first header, or a header-less doc.)
        header_of: List[Optional[str]] = [None] * n   # section a header opens
        is_header: List[bool] = [False] * n
        zone: List[Optional[str]] = [None] * n
        current: Optional[str] = None
        for i, t in enumerate(texts):
            h = _looks_like_header(t)
            if h in ("education", "experience"):
                current = h
                header_of[i] = h
                is_header[i] = True
                zone[i] = None            # the header line itself isn't content
            elif h == "other":
                current = "other"         # explicit non-target zone
                is_header[i] = True
                zone[i] = None
            else:
                zone[i] = current

        has_edu_header = any(hh == "education" for hh in header_of)
        has_exp_header = any(hh == "experience" for hh in header_of)

        # 2) Model pass → per-paragraph entity vote.
        votes = self._model_votes(texts)

        # 3) Resolve.
        #    Rule of precedence (headers are authoritative when present):
        #      * inside an edu/exp header zone  -> that section
        #      * inside an explicit 'other' zone -> NEVER assigned, and the model
        #        is NOT allowed to override it (this was the bug: overfit models
        #        tag spurious entities in SKILLS/SUMMARY lines)
        #      * no header context (preamble or header-less doc) -> trust the
        #        model, but only for a section that has NO header of its own
        #        (so a doc with an EXPERIENCE header but no EDUCATION header can
        #        still recover education paragraphs, while a fully-headered doc
        #        never leaks preamble lines into a section).
        section: List[Optional[str]] = [None] * n
        for i in range(n):
            if is_header[i]:
                continue
            z = zone[i]
            if z in ("education", "experience"):
                section[i] = z
            elif z == "other":
                section[i] = None
            else:  # z is None
                v = votes[i]
                if v == "education" and not has_edu_header:
                    section[i] = "education"
                elif v == "experience" and not has_exp_header:
                    section[i] = "experience"
                # else leave None (fully-headered doc → preamble stays out)

        # 3b) Contiguity smoothing: a lone gap between two paragraphs of the SAME
        #     section adopts that section (helps blank/very-short lines mid-block).
        #     Never bridges across a header or an explicit 'other' zone.
        for i in range(1, n - 1):
            if section[i] is None and not is_header[i] and zone[i] != "other":
                prev_s, next_s = section[i - 1], section[i + 1]
                if prev_s is not None and prev_s == next_s:
                    section[i] = prev_s

        # 4) Group into the SectionParser-style dict.
        out: Dict[str, List[Pair]] = defaultdict(list)
        for i, p in enumerate(pairs):
            if is_header[i] and header_of[i] and self.include_header_paragraph:
                out[header_of[i]].append(p)
            if section[i] in ("education", "experience"):
                out[section[i]].append(p)
        return {"education": out.get("education", []),
                "experience": out.get("experience", [])}

    # ── parity with SectionParser.section_text ───────────────────────────────
    @staticmethod
    def section_text(section_pairs: List[Pair]) -> str:
        return "\n".join(_ptext(p) for p in section_pairs).strip()
