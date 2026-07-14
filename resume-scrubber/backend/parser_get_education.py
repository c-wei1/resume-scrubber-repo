import re
from typing import Any, Dict, List, Optional


class EducationParser:
    """Parse the Education section into structured entries."""

    DEGREE_PATTERNS = [
        # Full words
        "bachelor", "master", "doctor", "doctorate", "doctoral",
        "associate", "diploma", "postgraduate", "undergraduate",
        # Common abbreviations
        "phd", "ph.d", "edd", "ed.d", "dba", "d.b.a",
        "md", "m.d", "do", "d.o", "dds", "d.d.s", "dmd", "d.m.d",
        "jd", "j.d", "llb", "ll.b", "llm", "ll.m",
        "mba", "m.b.a", "mpa", "m.p.a", "mph", "m.p.h",
        "mfa", "m.f.a", "mlis", "msw", "m.s.w",
        "bs", "b.s", "bsc", "b.sc",
        "ba", "b.a", "bba", "b.b.a", "bfa", "b.f.a",
        "beng", "b.eng", "btech", "b.tech",
        "ms", "m.s", "msc", "m.sc",
        "ma", "m.a", "med", "m.ed",
        "meng", "m.eng", "mtech", "m.tech",
        "mphil", "m.phil", "mres", "m.res",
        "as", "a.s", "aa", "a.a", "aas", "a.a.s",
        "major", "minor", "concentration",
        "honours", "honors", "hons",
        # Levels
        "a level", "as level", "gcse", "gcses",
        "o level", "a-level", "as-level",
        "ib", "ged", "hnd", "hnc", "btec",
    ]

    SCHOOL_PATTERNS = [
        "university", "college", "institute",
        "school", "academy", "polytechnic",
        "conservatory", "seminary", "université",
        "universität", "universidad",
    ]

    CERT_PATTERNS = [
        "certification", "certified", "certificate",
        "license", "credential",
    ]

    # Date regex supporting both 2-digit and 4-digit years
    DATE_STRIP_RE = re.compile(
        r"\(?\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+)?"
        r"(?:(?:19|20)?\d{2})"
        r"(?:\s*(?:-|–|—|to)\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?\s+)?"
        r"(?:(?:(?:19|20)?\d{2})|Present|Current|Now|Ongoing))?"
        r"\s*\)?",
        re.IGNORECASE,
    )

    # Max words for a line to be considered an education entry
    ENTRY_MAX_WORDS = 13

    NEWLINE_TAG_RE = re.compile(r"^\[NEWLINE\]\s*", re.IGNORECASE)

    # ─────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _strip_dates(value: str) -> str:
        if not value:
            return value
        cleaned = value.replace("\xa0", " ")
        cleaned = EducationParser.DATE_STRIP_RE.sub("", cleaned)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = cleaned.strip(" \t-–—,|()")
        return cleaned

    @staticmethod
    def _contains_any(line: str, patterns: List[str]) -> bool:
        line_l = line.lower()
        for p in patterns:
            if re.search(rf"\b{re.escape(p.lower())}\b", line_l):
                return True
        return False

    @staticmethod
    def _extract_year(line: str) -> str:
        if not line:
            return ""
        m = EducationParser.DATE_STRIP_RE.search(line)
        if not m:
            return ""
        return m.group(0).strip(" \t()[]{}").strip()

    @staticmethod
    def _is_short_enough(line: str) -> bool:
        """Only consider lines with 13 words or fewer as education entries."""
        return len(line.split()) <= EducationParser.ENTRY_MAX_WORDS

    @staticmethod
    def _append_unique(existing: str, new_part: str) -> str:
        """Append new_part to existing with ' | ' separator, avoiding duplicates."""
        if not existing:
            return new_part
        existing_parts = [p.strip() for p in existing.split(" | ") if p.strip()]
        if any(p.lower() == new_part.lower() for p in existing_parts):
            return existing
        return existing + " | " + new_part

    @staticmethod
    def _has_content(entry: Dict) -> bool:
        if entry.get("type") == "school":
            school = entry.get("school", {})
            return any(str(v).strip() for v in school.values())
        if entry.get("type") == "certification":
            cert = entry.get("certification", {})
            return any(str(v).strip() for v in cert.values())
        return False

    # ─────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def parse(text: str) -> List[Dict[str, Any]]:
        """
        Output schema:

        [
            {
                "type": "school",
                "school": {
                    "institution_header": "University of Birmingham | PhD: Cancer Sciences",
                    "year": "Sept 09 - Sept 13"
                }
            },
            {
                "type": "certification",
                "certification": {
                    "name": "...",
                    "year": ""
                }
            }
        ]
        """
        entries: List[Dict[str, Any]] = []

        lines = [
            line.strip()
            for line in text.split("\n")
            if line.strip()
        ]

        current_school: Optional[Dict[str, Any]] = None
        current_cert: Optional[Dict[str, Any]] = None

        def finalize_school() -> None:
            nonlocal current_school
            if current_school and EducationParser._has_content(current_school):
                entries.append(current_school)
            current_school = None

        def finalize_cert() -> None:
            nonlocal current_cert
            if current_cert and EducationParser._has_content(current_cert):
                entries.append(current_cert)
            current_cert = None

        for line in lines:
            # Skip lines that are too long to be education entries
            if not EducationParser._is_short_enough(line):
                continue

            has_degree = EducationParser._contains_any(line, EducationParser.DEGREE_PATTERNS)
            has_school = EducationParser._contains_any(line, EducationParser.SCHOOL_PATTERNS)
            has_cert = EducationParser._contains_any(line, EducationParser.CERT_PATTERNS)
            year = EducationParser._extract_year(line)

            # ── Certification branch ─────────────────────────────
            if has_cert:
                finalize_school()
                if current_cert is None:
                    current_cert = {
                        "type": "certification",
                        "certification": {"name": "", "year": ""}
                    }
                if not current_cert["certification"]["name"]:
                    current_cert["certification"]["name"] = line
                if year and not current_cert["certification"]["year"]:
                    current_cert["certification"]["year"] = year
                continue

            # ── Degree and/or school on same line ────────────────
            if has_degree or has_school:
                finalize_cert()

                # If we see a school keyword and current entry already
                # has a school keyword in its header, start a new entry
                if has_school and current_school is not None:
                    existing = current_school["school"]["institution_header"]
                    if EducationParser._contains_any(existing, EducationParser.SCHOOL_PATTERNS):
                        finalize_school()

                # If we see a degree keyword and current entry already
                # has a degree keyword in its header, start a new entry
                if has_degree and current_school is not None:
                    existing = current_school["school"]["institution_header"]
                    if EducationParser._contains_any(existing, EducationParser.DEGREE_PATTERNS):
                        finalize_school()

                if current_school is None:
                    current_school = {
                        "type": "school",
                        "school": {"institution_header": "", "year": ""}
                    }

                # Append line to institution_header
                current_school["school"]["institution_header"] = (
                    EducationParser._append_unique(
                        current_school["school"]["institution_header"],
                        line,
                    )
                )

                if year and not current_school["school"]["year"]:
                    current_school["school"]["year"] = year
                continue

            # ── Date-only or date continuation line ──────────────
            if year:
                if current_school is not None and not current_school["school"]["year"]:
                    current_school["school"]["year"] = year
                elif current_cert is not None and not current_cert["certification"]["year"]:
                    current_cert["certification"]["year"] = year
                continue

            # ── Continuation: unrecognized short line ────────────
            # Could be a sub-detail (e.g. "A level: 3A's"); skip it
            # since it doesn't contain degree/school/cert keywords.

        finalize_school()
        finalize_cert()
        return entries
