import os
import re
import pickle
from typing import Any, Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# Load trained models once at module level
# ─────────────────────────────────────────────────────────────────────────────
_MODEL_DIR = os.path.dirname(os.path.realpath(__file__))

with open(os.path.join(_MODEL_DIR, "title_vectorizer.pkl"), "rb") as f:
    _title_vectorizer = pickle.load(f)
with open(os.path.join(_MODEL_DIR, "title_model.pkl"), "rb") as f:
    _title_model = pickle.load(f)
with open(os.path.join(_MODEL_DIR, "company_vectorizer.pkl"), "rb") as f:
    _company_vectorizer = pickle.load(f)
with open(os.path.join(_MODEL_DIR, "company_model.pkl"), "rb") as f:
    _company_model = pickle.load(f)


def _clean_text(text: str) -> str:
    """Normalize text for model inference (mirrors nbc.py clean_text)."""
    text = re.sub(r"[^a-zA-Z0-9\s&/\-]", "", text)
    return text.lower().strip()


class ExperienceParser:
    """Parse the Experience section into structured job entries."""

    # ─── Date regex (mirrors education parser) ────────────────────────────────
    DATE_RE = re.compile(
        # Format 1: "Month Year" or "Month Year – Month Year/Present"
        r"\(?\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?"
        r"|(?:Spring|Summer|Fall|Winter|Autumn))\s+"
        r"(?:(?:19|20)?\d{2})"
        r"(?:\s*(?:-|–|—|to)\s*"
        r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)[a-z]*\.?"
        r"|(?:Spring|Summer|Fall|Winter|Autumn))?\s*"
        r"(?:(?:(?:19|20)?\d{2})|Present|Current|Now|Ongoing))?"
        r"\s*\)?"
        r"|"
        # Format 2: "YYYY/M/D" or "YYYY/MM" or "YYYY/MM/DD – YYYY/MM/DD"
        r"\(?\s*(?:19|20)\d{2}[/\-.]\d{1,2}(?:[/\-.]\d{1,2})?"
        r"(?:\s*(?:-|–|—|to)\s*"
        r"(?:(?:19|20)\d{2}[/\-.]\d{1,2}(?:[/\-.]\d{1,2})?"
        r"|Present|Current|Now|Ongoing))?"
        r"\s*\)?"
        r"|"
        # Format 3: standalone "YYYY" or "YYYY – YYYY/Present"
        r"\(?\s*(?:19|20)\d{2}"
        r"(?:\s*(?:-|–|—|to)\s*"
        r"(?:(?:19|20)\d{2}|Present|Current|Now|Ongoing))?"
        r"\s*\)?",
        re.IGNORECASE,
    )

    # Probability thresholds for classification
    TITLE_THRESHOLD = 0.90
    COMPANY_THRESHOLD = 0.75

    # A title segment must be short to avoid false positives on descriptions
    TITLE_MAX_WORDS = 6
    # Company names are also short
    COMPANY_MAX_WORDS = 5

    # Lines longer than this are likely descriptions, not headers
    HEADER_MAX_WORDS = 20
    HEADER_MAX_CHARS = 150

    # Max length for a no-date line to even attempt classification
    CLASSIFY_MAX_CHARS = 100

    # Bullet prefixes that signal a description line
    BULLET_RE = re.compile(r"^[\s]*[•·▪▸►\-\*\u2022\u2023\u25E6\u2043\u2219]+\s")

    # Common action verbs that start description bullets (past tense)
    ACTION_VERBS = {
        "achieved", "acted", "adapted", "administered", "advised", "aligned",
        "allocated", "analyzed", "applied", "appointed", "approved",
        "architected", "arranged", "assembled", "assessed", "assigned",
        "assisted", "attained", "audited", "authored", "automated",
        "balanced", "budgeted", "built", "calculated", "captured",
        "chaired", "championed", "coached", "collaborated", "collected",
        "communicated", "compiled", "completed", "composed", "computed",
        "conceived", "conceptualized", "condensed", "conducted", "consolidated",
        "constructed", "consulted", "contributed", "controlled", "converted",
        "coordinated", "counseled", "crafted", "created", "cultivated",
        "customized", "decreased", "defined", "delegated", "delivered",
        "demonstrated", "deployed", "designed", "detected", "determined",
        "developed", "devised", "diagnosed", "directed", "discovered",
        "dispatched", "distinguished", "distributed", "documented", "doubled",
        "drafted", "drove", "earned", "edited", "educated", "effected",
        "eliminated", "enabled", "encouraged", "enforced", "engineered",
        "enhanced", "ensured", "established", "evaluated", "examined",
        "exceeded", "executed", "expanded", "expedited", "experimented",
        "explained", "explored", "facilitated", "finalized", "fixed",
        "focused", "forecasted", "formalized", "formed", "formulated",
        "fortified", "founded", "fulfilled", "gathered", "generated",
        "governed", "grew", "guided", "handled", "headed", "helped",
        "hired", "identified", "illustrated", "implemented", "improved",
        "increased", "influenced", "informed", "initiated", "innovated",
        "inspected", "inspired", "installed", "instituted", "integrated",
        "interpreted", "introduced", "invented", "investigated", "launched",
        "led", "leveraged", "liaised", "maintained", "managed", "mapped",
        "marketed", "maximized", "measured", "mediated", "mentored",
        "merged", "migrated", "minimized", "mobilized", "modeled",
        "modernized", "modified", "monitored", "motivated", "navigated",
        "negotiated", "obtained", "operated", "optimized", "orchestrated",
        "organized", "originated", "outlined", "overcame", "overhauled",
        "oversaw", "partnered", "performed", "persuaded", "piloted",
        "pioneered", "planned", "prepared", "presented", "presided",
        "prevented", "prioritized", "processed", "produced", "programmed",
        "projected", "promoted", "proposed", "provided", "published",
        "purchased", "pursued", "qualified", "raised", "ranked",
        "reached", "realigned", "rebuilt", "received", "recommended",
        "reconciled", "recruited", "redesigned", "reduced", "refined",
        "registered", "regulated", "rehabilitated", "reinforced", "rejuvenated",
        "related", "remodeled", "rendered", "reorganized", "repaired",
        "replaced", "reported", "represented", "researched", "reshaped",
        "resolved", "restored", "restructured", "retained", "retrieved",
        "revamped", "reviewed", "revised", "revitalized", "revolutionized",
        "saved", "scheduled", "secured", "selected", "served", "shaped",
        "shared", "shipped", "simplified", "solved", "spearheaded",
        "specialized", "specified", "sponsored", "stabilized", "staffed",
        "standardized", "steered", "stimulated", "streamlined", "strengthened",
        "structured", "succeeded", "summarized", "supervised", "supported",
        "surpassed", "surveyed", "sustained", "synthesized", "systematized",
        "targeted", "taught", "tested", "trained", "transcribed",
        "transformed", "translated", "transmitted", "tripled", "troubleshot",
        "uncovered", "unified", "updated", "upgraded", "utilized",
        "validated", "verified", "visualized", "volunteered", "won", "worked", "wrote",
    }

    @staticmethod
    def _starts_with_action_verb(line: str) -> bool:
        """Check if line starts with a common resume action verb (past or present participle)."""
        words = line.split()
        if not words:
            return False
        # First word: check explicit list AND present participle (-ing)
        first = words[0].lower().rstrip(",;:")
        if first in ExperienceParser.ACTION_VERBS:
            return True
        if first.endswith("ing") and len(first) > 4:
            return True
        # Second word: check explicit list only (avoids false positives
        # on company names like "Atelier Consulting")
        if len(words) > 1:
            second = words[1].lower().rstrip(",;:")
            if second in ExperienceParser.ACTION_VERBS:
                return True
        return False

    @staticmethod
    def _is_section_marker(line: str) -> bool:
        """Check if line is a label/marker like 'Key Responsibilities:' or 'Focus: ...'"""
        # Line ends with colon
        if line.rstrip().endswith(":"):
            return True
        # Colon appears in the first few words ("Label: content" pattern)
        colon_pos = line.find(":")
        if colon_pos > 0:
            prefix = line[:colon_pos]
            if len(prefix.split()) <= 4:
                return True
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _extract_date(line: str) -> str:
        """Extract a date/date-range string from a line, or empty string."""
        m = ExperienceParser.DATE_RE.search(line)
        if m:
            return m.group(0).strip(" \t()[]{}").strip()
        return ""

    @staticmethod
    def _strip_date(line: str) -> str:
        """Remove date portion from a line."""
        return ExperienceParser.DATE_RE.sub("", line).strip(" \t,|•-–—")

    @staticmethod
    def _is_date_only(line: str) -> bool:
        """True if the line is nothing but a date expression."""
        stripped = ExperienceParser._strip_date(line)
        return len(stripped) == 0 and bool(ExperienceParser._extract_date(line))

    @staticmethod
    def _classify_line(line: str) -> Dict[str, float]:
        """
        Return title and company probabilities for a line.
        """
        cleaned = _clean_text(line)
        if not cleaned:
            return {"title_prob": 0.0, "company_prob": 0.0}

        t_vec = _title_vectorizer.transform([cleaned])
        c_vec = _company_vectorizer.transform([cleaned])

        title_prob = _title_model.predict_proba(t_vec)[0][1]
        company_prob = _company_model.predict_proba(c_vec)[0][1]

        return {"title_prob": title_prob, "company_prob": company_prob}

    @staticmethod
    def _is_header_candidate(line: str) -> bool:
        """Quick heuristic: headers are short-ish lines."""
        if len(line) > ExperienceParser.HEADER_MAX_CHARS:
            return False
        if len(line.split()) > ExperienceParser.HEADER_MAX_WORDS:
            return False
        return True

    @staticmethod
    def _split_header_segments(line: str) -> List[str]:
        """
        Split a header line into segments by common delimiters
        (pipe, bullet, em-dash, comma, 'at', '@') so we can classify
        each segment independently.
        """
        segments = re.split(r"\s*[|•·]\s*|\s+[-–—]\s+|\s+at\s+|\s*@\s*", line)
        # Also try comma split if only 1 segment came back
        if len(segments) == 1:
            segments = [s.strip() for s in line.split(",", maxsplit=1) if s.strip()]
        return [s.strip() for s in segments if s.strip()]

    # ─────────────────────────────────────────────────────────────────────────
    # Main entry point
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _is_title_or_company(line: str) -> bool:
        """Check if a line (or segment) classifies as a job title or company."""
        words = len(line.split())
        probs = ExperienceParser._classify_line(line)
        if (probs["title_prob"] >= ExperienceParser.TITLE_THRESHOLD
                and words <= ExperienceParser.TITLE_MAX_WORDS):
            return True
        if (probs["company_prob"] >= ExperienceParser.COMPANY_THRESHOLD
                and words <= ExperienceParser.COMPANY_MAX_WORDS):
            return True
        return False

    @staticmethod
    def parse(text: str) -> List[Dict[str, Any]]:
        """
        Parse experience section text into structured entries.

        Returns:
        [
            {
                "job_header": ["Software Engineer | Google Inc", "Jan 2020 - Present"],
                "description": [
                    "Built microservices architecture...",
                    "Led team of 5 engineers..."
                ]
            },
            ...
        ]
        """
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        entries: List[Dict[str, Any]] = []
        current_entry: Optional[Dict[str, Any]] = None
        in_description = False
        current_entry_has_date = False

        def finalize_entry():
            nonlocal current_entry, in_description, current_entry_has_date
            if current_entry and current_entry["job_header"]:
                entries.append(current_entry)
            current_entry = None
            in_description = False
            current_entry_has_date = False

        for line in lines:
            date = ExperienceParser._extract_date(line)
            m = ExperienceParser.DATE_RE.search(line) if date else None
            date_at_start = m and m.start() <= 5 if m else False

            # ── 1. Obvious description lines (bullets, action verbs,
            #       section markers, long lines without dates) — always
            #       description regardless of any incidental dates ────
            is_obvious_description = (
                ExperienceParser.BULLET_RE.match(line)
                or ExperienceParser._starts_with_action_verb(line)
                or ExperienceParser._is_section_marker(line)
                or (len(line) > ExperienceParser.CLASSIFY_MAX_CHARS and not date)
            )

            if is_obvious_description:
                if current_entry is None:
                    current_entry = {"job_header": [], "description": []}
                current_entry["description"].append(line)
                in_description = True
                continue

            # ── 2. Lines with a date at the start → date-driven
            #       entry boundary logic ──────────────────────────────
            if date_at_start or (date and ExperienceParser._is_date_only(line)):
                if current_entry is not None and (
                    current_entry["description"] or current_entry_has_date
                ):
                    # Already have description or a date → new job
                    finalize_entry()
                    current_entry = {"job_header": [], "description": []}
                    current_entry["job_header"].append(line)
                elif current_entry is not None:
                    # Still building header, first date → append
                    current_entry["job_header"].append(line)
                else:
                    current_entry = {"job_header": [], "description": []}
                    current_entry["job_header"].append(line)
                current_entry_has_date = True
                in_description = False
                continue

            # ── 3. Classify the line with the NBC models ─────────────
            is_job_header = False
            segments = ExperienceParser._split_header_segments(line)
            for seg in segments:
                if ExperienceParser._is_title_or_company(seg):
                    is_job_header = True
                    break
            if not is_job_header and ExperienceParser._is_header_candidate(line):
                if ExperienceParser._is_title_or_company(line):
                    is_job_header = True

            if is_job_header:
                if in_description:
                    # New title/company after description → new job entry
                    finalize_entry()
                    current_entry = {"job_header": [line], "description": []}
                else:
                    # Still building header → append
                    if current_entry is None:
                        current_entry = {"job_header": [], "description": []}
                    current_entry["job_header"].append(line)
                in_description = False
                continue

            # ── 4. Mid-line date (not at start, not classified as
            #       header) → header continuation or new entry ────────
            if date:
                if in_description:
                    # Mid-line date after description → new entry
                    finalize_entry()
                    current_entry = {"job_header": [line], "description": []}
                    current_entry_has_date = True
                    in_description = False
                elif current_entry is not None:
                    # Still building header → append
                    current_entry["job_header"].append(line)
                    current_entry_has_date = True
                continue

            # ── 5. Fallback: unclassified line → description ─────────
            if current_entry is None:
                current_entry = {"job_header": [], "description": []}
            current_entry["description"].append(line)
            in_description = True

        finalize_entry()
        return entries
