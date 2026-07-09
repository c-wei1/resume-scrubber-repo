import re
class EducationParser:
    """Parse the Education section into structured entries."""

    DEGREE_PATTERNS = [
        "bachelor", "master", "doctor", "phd",
        "bs", "b.s", "ba", "b.a",
        "ms", "m.s", "ma", "m.a", "mba",
        "associate", "beng", "meng", "jd",
        "major", "minor",
    ]

    SCHOOL_PATTERNS = [
        "university", "college", "institute",
        "school", "academy", "polytechnic",
    ]

    CERT_PATTERNS = [
        "certification", "certified", "certificate",
        "license", "credential",
    ]

    YEAR_RE = r"\b(19|20)\d{2}\b"

    # YEAR_RANGE_RE = re.compile(
    #     r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    #     r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    #     r"Dec(?:ember)?)?\s*(?:19|20)\d{2}\b\s*(?:-|–|—|to)\s*"
    #     r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    #     r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    #     r"Dec(?:ember)?)?\s*(?:19|20)\d{2}\b",
    #     re.IGNORECASE,
    # )

    # Broad date-strip regex used when cleaning school names.
    # Matches: '2020', '2020-2024', 'Mar 2015 - Feb 2019', '(Aug 2018 – May 2022)',
    # 'Aug 2022 – Present', etc.
    DATE_STRIP_RE = re.compile(
        r"\(?\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+)?"
        r"(?:19|20)\d{2}"
        r"(?:\s*(?:-|–|—|to)\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+)?"
        r"(?:(?:19|20)\d{2}|Present|Current|Now|Ongoing))?"
        r"\s*\)?",
        re.IGNORECASE,
    )

    DEGREE_MAX_WORDS = 20     # Real degree lines are usually ≤ ~15 words
    DEGREE_MAX_CHARS = 150

    # Strip leading "[BULLET] " marker if present.
    NEWLINE_TAG_RE = re.compile(r"^\[NEWLINE\]\s*", re.IGNORECASE)

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _strip_newline_tag(line: str) -> str:
        """Remove a leading '[NEWLINE] ' marker if present."""
        return EducationParser.NEWLINE_TAG_RE.sub("", line).strip()

    @staticmethod
    def _strip_dates(value: str) -> str:
        """Remove year / year-range / month-year forms from a text fragment."""
        if not value:
            return value
        cleaned = value.replace("\xa0", " ")                 # nbsp → space
        cleaned = EducationParser.DATE_STRIP_RE.sub("", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)             # collapse spaces
        cleaned = cleaned.strip(" \t-–—,|()")                 # trim edge junk
        return cleaned

    @staticmethod
    def _contains_any(line: str, patterns: List[str]) -> bool:
        line_l = line.lower()
        for p in patterns:
            if re.search(rf"\b{re.escape(p.lower())}\b", line_l):
                return True
        return False


    @staticmethod
    def _looks_like_degree_entry(line: str) -> bool:
        """
        True only when the line both contains a degree keyword AND is
        short enough to plausibly be a degree entry (not prose that
        mentions a degree in passing).
        """
        if not EducationParser._contains_any(line, EducationParser.DEGREE_PATTERNS):
            return False
        stripped = EducationParser._strip_bullet_tag(line).strip()
        if len(stripped) > EducationParser.DEGREE_MAX_CHARS:
            return False
        if len(stripped.split()) > EducationParser.DEGREE_MAX_WORDS:
            return False
        if stripped.endswith("."):        # ends in a full sentence → likely prose
            return False
        return True

    @staticmethod
    def _extract_year(line: str) -> str:
        """Extract the date/year from a line (range, open-ended, or single)."""
        if not line:
            return ""
        m = EducationParser.DATE_STRIP_RE.search(line)
        if not m:
            return ""
        return m.group(0).strip(" \t()[]{}").strip()


    @staticmethod
    def _extract_school(line: str) -> str:
        # Prefer bullet/pipe-separated segment that contains a school keyword.
        chunks = [c.strip() for c in re.split(r"[•|]", line) if c.strip()]
        for chunk in chunks:
            if EducationParser._contains_any(chunk, EducationParser.SCHOOL_PATTERNS):
                return EducationParser._strip_dates(chunk)

        # Fallback: if the whole line looks like a school line, trim trailing
        # location/year noise and then also strip any remaining date fragments.
        if EducationParser._contains_any(line, EducationParser.SCHOOL_PATTERNS):
            cleaned = re.split(r",|\b(?:19|20)\d{2}\b", line, maxsplit=1)[0].strip(" -–—,")
            return EducationParser._strip_dates(cleaned).strip()
        return ""

    @staticmethod
    def _append_degree(existing: str, new_degree: str) -> str:
        if not existing:
            return new_degree
        existing_parts = [p.strip() for p in existing.split(" | ") if p.strip()]
        if any(p.lower() == new_degree.lower() for p in existing_parts):
            return existing
        return existing + " | " + new_degree

    @staticmethod
    def _has_content(entry: Dict[str, str]) -> bool:
        return any(v.strip() for v in entry.values())

    # ─────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def parse(text: str) -> List[Dict[str, Any]]:
        """
        Parse education section into entries using keyword-based detection.

        Output schema per entry:
            {"degree": "", "school": "", "year": ""}
        or
            {"certification": "", "year": ""}
        """
        entries: List[Dict[str, str]] = []

        # 1) Preprocess: split lines, drop empties, strip any [BULLET] tag.
        lines = [
            EducationParser._strip_bullet_tag(line)
            for line in text.split("\n")
            if line.strip()
        ]
        lines = [line for line in lines if line]

        current_degree: Optional[Dict[str, str]] = None
        current_cert: Optional[Dict[str, str]] = None

        def finalize_degree() -> None:
            nonlocal current_degree
            if current_degree and EducationParser._has_content(current_degree):
                entries.append(current_degree)
            current_degree = None

        def finalize_cert() -> None:
            nonlocal current_cert
            if current_cert and EducationParser._has_content(current_cert):
                entries.append(current_cert)
            current_cert = None

        for line in lines:
            has_degree = EducationParser._looks_like_degree_entry(line)
            has_school = EducationParser._contains_any(line, EducationParser.SCHOOL_PATTERNS)
            has_cert   = EducationParser._contains_any(line, EducationParser.CERT_PATTERNS)
            year       = EducationParser._extract_year(line)
            school     = EducationParser._extract_school(line)

            # ── Certification branch ─────────────────────────────
            if has_cert:
                finalize_degree()
                if current_cert is None:
                    current_cert = {"certification": "", "year": ""}
                if not current_cert["certification"]:
                    current_cert["certification"] = line
                if year and not current_cert["year"]:
                    current_cert["year"] = year
                continue

            # ── Degree / school branch ───────────────────────────
            if has_degree or has_school:
                finalize_cert()

                # Start a new degree entry only when the school changes.
                if (current_degree and school
                        and current_degree["school"]
                        and current_degree["school"].lower() != school.lower()):
                    finalize_degree()
                if current_degree is None:
                    current_degree = {"degree": "", "school": "", "year": ""}

                if has_school and school and not current_degree["school"]:
                    current_degree["school"] = school

                if has_degree:
                    current_degree["degree"] = EducationParser._append_degree(
                        current_degree["degree"], line
                    )

                if year and not current_degree["year"]:
                    current_degree["year"] = year
                continue

            # ── Continuation line: fill missing fields on active entry ──
            if current_degree is not None:
                if year and not current_degree["year"]:
                    current_degree["year"] = year
                elif not current_degree["degree"]:
                    current_degree["degree"] = line
            elif current_cert is not None:
                if year and not current_cert["year"]:
                    current_cert["year"] = year
                elif not current_cert["certification"]:
                    current_cert["certification"] = line

        finalize_degree()
        finalize_cert()
        return entries