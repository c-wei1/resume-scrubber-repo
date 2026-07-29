"""
SectionParser
=============

Given a list of (text, <w:p>) pairs from TextExtractor, group them into
resume sections. Both the text-based downstream parsers (Education,
Experience) and the template populator (which needs the underlying XML)
consume the same segmentation, so they can never disagree.

Public API
----------
    find_sections(pairs)          → Dict[section, List[(text, xml)]]
    section_text(pairs_in_sec)    → str    (helper to join for text parsers)
    section_xml(pairs_in_sec)     → List[<w:p>]  (deepcopied for insertion)
"""

import re
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

# A pair is (cleaned_text, w:p element). We accept "Any" for the xml side to
# avoid a hard lxml import here — the module still works with plain tuples.
Pair = Tuple[str, object]


class SectionParser:
    """Identify and extract sections from resume text/xml pairs."""

    SECTION_KEYWORDS = {
        "experience": [
            "experience", "work experience", "working experience",
            "professional experience", "employment", "employment history",
            "employment experience", "career", "career history",
            "career experience", "work history", "job history",
            "relevant experience", "relevant work experience",
            "related experience", "industry experience",
            "corporate experience", "business experience",
            "consulting experience", "freelance experience",
            "freelance work", "contract experience", "contract work",
            "additional experience", "other experience",
            "prior experience", "previous experience", "recent experience",
            "current experience", "selected experience",
            "featured experience", "academic experience",
            "academic appointments", "appointments", "academic positions",
            "faculty appointments", "faculty positions",
            "research experience", "research positions",
            "research appointments", "research", "research activities",
            "postdoctoral experience", "postdoctoral appointments",
            "fellowships", "fellowship experience",
            "visiting appointments", "visiting positions",
            "sabbatical appointments", "adjunct appointments",
            "teaching", "teaching experience", "teaching positions",
            "teaching appointments", "courses taught",
            "instructional experience", "educational experience",
            "pedagogical experience", "mentoring", "mentorship",
            "student mentoring", "advising", "clinical experience",
            "clinical practice", "clinical rotations", "rotations",
            "clerkships", "clinical training", "residency", "fellowship",
            "medical experience", "patient care experience",
            "surgical experience", "leadership", "leadership experience",
            "leadership roles", "leadership and activities",
            "professional and leadership experience",
            "volunteer experience", "volunteer work", "volunteering",
            "community service", "community involvement",
            "community engagement", "civic engagement", "service",
            "public service", "board service", "board memberships",
            "board positions", "boards and committees",
            "committee service", "advisory roles",
            "advisory board positions", "governance", "internships",
            "internship experience", "co-op experience",
            "cooperative education", "summer experience",
            "summer employment", "apprenticeships", "trainee positions",
            "student experience", "extracurricular experience",
            "military experience", "military service",
            "armed forces service", "active duty", "veteran experience",
            "professional service", "editorial service", "editorial roles",
            "editorial positions", "editorial board",
            "editorial board service", "journal editorships",
            "peer review", "peer review service", "reviewer",
            "reviewer service", "consulting", "consultancies",
            "consultancy roles", "external service", "university service",
            "departmental service", "institutional service",
            "committee memberships",
        ],
        "education": [
            "education", "educational background", "educational history",
            "educational qualifications", "academic background",
            "academic qualifications", "academic history",
            "academic studies", "academics", "degrees earned",
            "academic credentials", "formal education", "higher education",
            "undergraduate education", "graduate education",
            "postgraduate education", "professional education",
            "coursework", "relevant coursework", "selected coursework",
            "course highlights", "study abroad", "international studies",
            "exchange programs", "education and additional experiences",
            "education and experiences",
            "education and additional information",
        ],
        "other": [
            "experience and research areas", "experience and research",
            "research areas", "research projects",
            "training", "professional training", "professional development",
            "trainings and workshops", "workshops", "seminars",
            "continuing education", "executive education",
            "continuing professional development", "cpd",
            "continuing medical education", "cme", "bootcamps",
            "career development", "learning and development",
            "certification", "certifications", "certificates",
            "professional certifications", "certifications and licenses",
            "licenses", "licensure", "professional licenses",
            "credentials", "professional credentials", "accreditations",
            "registrations", "board certifications",
            "compliance training", "security clearances", "clearances",
            "government clearances", "contact", "contact information",
            "personal details", "personal information", "personal data",
            "biographical information", "bio", "header", "summary",
            "professional summary", "career summary", "executive summary",
            "qualifications summary", "summary of qualifications",
            "summary of skills and experience", "profile",
            "professional profile", "career profile", "personal profile",
            "objective", "career objective", "professional objective",
            "about me", "about", "overview", "career overview",
            "introduction", "highlights", "career highlights",
            "key highlights", "value proposition", "executive brief",
            "mission statement", "skills", "skill set", "core skills",
            "core competencies", "competencies", "key skills",
            "key competencies", "technical skills",
            "technical competencies", "technical expertise",
            "technical proficiencies", "technology skills",
            "software skills", "hardware skills",
            "tools and technologies", "technologies",
            "programming languages", "programming skills", "coding skills",
            "development skills", "frameworks and libraries", "platforms",
            "systems", "databases", "development tools",
            "analytical skills", "quantitative skills",
            "statistical skills", "data skills", "data analysis",
            "data science skills", "research skills", "laboratory skills",
            "lab techniques", "clinical skills", "soft skills",
            "interpersonal skills", "transferable skills",
            "personal skills", "professional skills", "managerial skills",
            "leadership skills", "communication skills",
            "presentation skills", "writing skills", "editorial skills",
            "language skills", "creative skills", "design skills",
            "additional skills", "other skills", "miscellaneous skills",
            "areas of expertise", "expertise", "specializations",
            "specialties", "domains of expertise", "functional expertise",
            "industry expertise", "strengths",
            "highlights of qualifications", "publications", "publication",
            "publication list", "peer-reviewed publications",
            "refereed publications", "journal articles",
            "journal publications", "peer-reviewed articles",
            "book chapters", "books", "authored books", "edited volumes",
            "manuscripts", "manuscripts in preparation",
            "manuscripts under review", "preprints", "working papers",
            "white papers", "technical reports", "reports", "book reviews",
            "editorials", "op-eds", "media contributions",
            "media coverage", "selected publications",
            "recent publications", "publications and presentations",
            "presentations", "presentation", "talks", "invited talks",
            "invited lectures", "invited presentations",
            "keynote presentations", "keynote addresses", "keynotes",
            "conference presentations", "conference talks",
            "conference proceedings", "poster presentations",
            "oral presentations", "selected presentations",
            "guest lectures", "public lectures", "speaking engagements",
            "panel discussions", "panels", "symposia",
            "workshops presented", "media appearances",
            "radio and podcast appearances", "grants", "grant funding",
            "research funding", "funding", "funded research",
            "sponsored research", "grants and awards", "grants received",
            "fellowships and grants", "contracts", "awarded contracts",
            "external funding", "internal funding", "awards", "honors",
            "honors and awards", "awards and honors",
            "awards and recognition", "achievements",
            "achievements and awards", "recognitions",
            "distinctions", "scholarships",
            "fellowships and scholarships", "prizes", "nominations",
            "academic honors", "academic awards", "professional honors",
            "professional recognition", "selected honors",
            "notable achievements", "career achievements",
            "projects", "personal projects",
            "side projects", "professional projects", "selected projects",
            "key projects", "featured projects", "notable projects",
            "recent projects", "portfolio", "portfolio highlights",
            "case studies", "product portfolio", "academic projects",
            "capstone projects", "independent projects",
            "software projects", "development projects", "open source",
            "open source contributions", "contributions",
            "professional affiliations", "affiliations",
            "professional memberships", "memberships",
            "society memberships", "association memberships",
            "professional organizations", "professional associations",
            "societies", "learned societies", "networks",
            "professional networks", "languages", "language proficiency",
            "foreign languages", "spoken languages", "fluencies",
            "multilingual skills", "interests", "personal interests",
            "hobbies", "hobbies and interests",
            "extracurricular interests", "extracurricular activities",
            "activities", "activities and interests", "passions",
            "outside interests", "volunteer interests", "references",
            "professional references", "academic references",
            "references available upon request", "referees", "nationality",
            "citizenship", "date of birth", "marital status",
            "photograph", "id", "identity", "curriculum vitae",
            "career path", "achievements and recognition",
            "professional synopsis", "career snapshot", "areas of interest",
            "personal vitae", "bio-data", "portfolio samples",
            "selected works", "works", "exhibitions", "solo exhibitions",
            "group exhibitions", "curatorial work", "performances",
            "selected performances", "repertoire", "discography",
            "filmography", "commissions", "residencies",
            "artist statement", "reviews", "press", "press coverage",
            "screenings", "technical projects", "technical portfolio",
            "github", "repositories", "coding challenges", "hackathons",
            "tech talks", "blog posts", "technical writing",
            "contributions to community", "vitae", "statement of purpose",
            "research statement", "teaching statement",
            "teaching philosophy", "diversity statement", "dei statement",
            "statement of contributions", "doctoral advisees",
            "postdoctoral advisees", "graduate students supervised",
            "undergraduate students supervised", "committees served",
            "thesis committees", "dissertation committees",
            "reading groups", "academic service", "reviewing service",
            "editorial boards served", "ad hoc reviewer",
            "symposia organized", "conferences organized",
            "executive profile", "executive highlights",
            "board experience", "board of directors",
            "corporate governance", "strategic leadership",
            "corporate boards", "financial highlights", "p&l ownership",
            "m&a experience", "turnaround experience", "growth highlights",
            "additional information", "additional details",
            "miscellaneous", "other", "notes", "appendix", "attachments",
            "supplemental information", "personal attributes",
            "characteristics", "career notes",
        ],
    }

    CONT_RE = re.compile(r"\s*\((?:cont\.?|continued)\)\s*$", re.IGNORECASE)

    COMPANY_SUFFIXES = {
        "inc", "incorporated", "llc", "ltd", "limited", "corp",
        "corporation", "co", "company", "group", "holdings", "gmbh",
        "sa", "ag", "bv", "nv", "plc", "spa", "kk", "pte", "pvt",
        "partners", "associates",
    }

    _DOI_RE = re.compile(r'doi[:\s]|https?://doi\.org/', re.IGNORECASE)
    _CITATION_RE = re.compile(
        r'\d{4}\s*;\s*\d+\s*\('
        r'|\d{4}\s*;\s*\d+\s*:'
        r'|\b(?:vol|pp|pages?)\b'
        r'|\bIn\s+press\b'
        r'|\bet\s+al\b',
        re.IGNORECASE,
    )
    _AUTHOR_LIST_RE = re.compile(
        r'^[A-Z][a-z]+\s+[A-Z]{1,2},'
        r'.*[A-Z][a-z]+\s+[A-Z]{1,2}'
    )

    _CANONICAL_KEYWORD_TO_SECTION: Dict[str, str] = {}

    # ─────────────────────────────────────────────────────────────
    # Header detection
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _normalize_header_text(text: str) -> str:
        text = re.sub(
            r'\b(?:[A-Za-z]\s+){2,}[A-Za-z]\b',
            lambda m: m.group(0).replace(" ", ""),
            text,
        )
        text = re.sub(r'\s*&\s*', ' and ', text)
        text = re.sub(r"[^A-Za-z0-9']", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _canonical(value: str) -> str:
        if not value:
            return ""
        cleaned = SectionParser._normalize_header_text(value)
        cleaned = SectionParser.CONT_RE.sub("", cleaned)
        cleaned = cleaned.lower()
        return re.sub(r"[^a-z0-9]+", "", cleaned)

    @staticmethod
    def _get_canonical_lookup() -> Dict[str, str]:
        if not SectionParser._CANONICAL_KEYWORD_TO_SECTION:
            lookup: Dict[str, str] = {}
            for section, keywords in SectionParser.SECTION_KEYWORDS.items():
                for kw in keywords:
                    lookup[SectionParser._canonical(kw)] = section
            SectionParser._CANONICAL_KEYWORD_TO_SECTION = lookup
        return SectionParser._CANONICAL_KEYWORD_TO_SECTION

    @staticmethod
    def _word_ratio_match(line: str) -> Optional[str]:
        line = SectionParser._normalize_header_text(line)
        line_words = re.findall(r"[a-z0-9]+", line.lower())
        if not line_words:
            return None
        line_word_count = len(line_words)

        keyword_pairs = [
            (kw, section)
            for section, keywords in SectionParser.SECTION_KEYWORDS.items()
            for kw in keywords
        ]
        keyword_pairs.sort(key=lambda p: len(p[0].split()), reverse=True)

        matches = []
        for kw, section in keyword_pairs:
            kw_words = re.findall(r"[a-z0-9]+", kw.lower())
            if not kw_words:
                continue
            kw_word_count = len(kw_words)
            if kw_word_count / line_word_count < 0.5:
                continue
            for i in range(line_word_count - kw_word_count + 1):
                if line_words[i:i + kw_word_count] == kw_words:
                    matches.append((kw_word_count, i, section))
                    break

        if not matches:
            return None
        matches.sort(key=lambda m: (m[0], m[1]), reverse=True)
        return matches[0][2]

    @staticmethod
    def _build_line_counts(pairs: List[Pair]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for text, _ in pairs:
            stripped = text.strip()
            if not stripped:
                continue
            canon = SectionParser._canonical(stripped)
            if not canon:
                continue
            counts[canon] = counts.get(canon, 0) + 1
        return counts

    @staticmethod
    def is_section_header(line: str, line_counts: Dict[str, int]) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        if stripped.endswith(".") or stripped.endswith(":") or len(stripped) > 120:
            return False
        canon = SectionParser._canonical(stripped)
        if not canon or len(canon) > 40:
            return False
        # Uniqueness gate
        if line_counts.get(canon, 0) != 1:
            return False
        if canon in SectionParser._get_canonical_lookup():
            return True
        if SectionParser._word_ratio_match(stripped) is not None:
            return True
        return False

    @staticmethod
    def match_section_key(line: str, line_counts: Dict[str, int]) -> Optional[str]:
        if not SectionParser.is_section_header(line, line_counts):
            return None
        canon = SectionParser._canonical(line.strip())
        lookup = SectionParser._get_canonical_lookup()
        if canon in lookup:
            return lookup[canon]
        return SectionParser._word_ratio_match(line.strip())

    @staticmethod
    def _looks_like_publication(line: str) -> bool:
        stripped = line.strip()
        if not stripped or len(stripped) < 40:
            return False
        if SectionParser._DOI_RE.search(stripped):
            return True
        if SectionParser._CITATION_RE.search(stripped):
            return True
        if SectionParser._AUTHOR_LIST_RE.match(stripped):
            return True
        return False

    # ─────────────────────────────────────────────────────────────
    # Main entry point — operates on (text, xml) pairs
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def find_sections(pairs: List[Pair]) -> Dict[str, List[Pair]]:
        """
        Group (text, xml) pairs into sections.

        Returns:
            {
                "header":     [(text, xml), ...],
                "education":  [(text, xml), ...],
                "experience": [(text, xml), ...],
                "other":      [(text, xml), ...],
                ...
            }

        Both text-based downstream parsers and template population code
        consume this same dict, so they cannot disagree about which lines
        belong where.
        """
        pairs = list(pairs)
        line_counts = SectionParser._build_line_counts(pairs)

        sections: Dict[str, List[Pair]] = {"header": []}
        current = "header"

        for text, xml in pairs:
            if SectionParser.is_section_header(text, line_counts):
                key = (
                    SectionParser.match_section_key(text, line_counts)
                    or "other"
                )
                current = key
                sections.setdefault(current, [])
                continue

            if not text.strip():
                continue

            # Detect publications bleeding into an experience section
            if (
                current == "experience"
                and SectionParser._looks_like_publication(text)
            ):
                current = "other"
                sections.setdefault(current, [])

            sections.setdefault(current, []).append((text, xml))

        return sections

    # ─────────────────────────────────────────────────────────────
    # Convenience helpers
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def section_text(section_pairs: List[Pair]) -> str:
        """Join a section's pairs back into a single '\\n'-separated string."""
        return "\n".join(text for text, _ in section_pairs)

    @staticmethod
    def section_xml(section_pairs: List[Pair]) -> List[object]:
        """Return DEEP-COPIED <w:p> elements ready to be inserted elsewhere."""
        return [deepcopy(xml) for _, xml in section_pairs if xml is not None]
