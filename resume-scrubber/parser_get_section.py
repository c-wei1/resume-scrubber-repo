import re
from typing import Dict, List, Optional

class SectionParser:
    """Identify and extract sections from resume text."""

    SECTION_KEYWORDS = {
        "experience": [
            "experience",
            "work experience",
            "working experience",
            "professional experience",
            "employment",
            "employment history",
            "employment experience",
            "career",
            "career history",
            "career experience",
            "work history",
            "job history",
            "relevant experience",
            "relevant work experience",
            "related experience",
            "industry experience",
            "corporate experience",
            "business experience",
            "consulting experience",
            "freelance experience",
            "freelance work",
            "contract experience",
            "contract work",
            "additional experience",
            "other experience",
            "prior experience",
            "previous experience",
            "recent experience",
            "current experience",
            "selected experience",
            "featured experience",
            "academic experience",
            "academic appointments",
            "appointments",
            "academic positions",
            "faculty appointments",
            "faculty positions",
            "research experience",
            "research positions",
            "research appointments",
            "research",
            "research activities",
            "research projects",
            "postdoctoral experience",
            "postdoctoral appointments",
            "graduate research",
            "undergraduate research",
            "doctoral research",
            "fellowships",
            "fellowship experience",
            "visiting appointments",
            "visiting positions",
            "sabbatical appointments",
            "adjunct appointments",
            "teaching",
            "teaching experience",
            "teaching positions",
            "teaching appointments",
            "courses taught",
            "instructional experience",
            "educational experience",
            "pedagogical experience",
            "mentoring",
            "mentorship",
            "student mentoring",
            "advising",
            "clinical experience",
            "clinical practice",
            "clinical rotations",
            "rotations",
            "clerkships",
            "clinical training",
            "residency",
            "fellowship",
            "medical experience",
            "patient care experience",
            "surgical experience",
            "leadership",
            "leadership experience",
            "leadership roles",
            "leadership and activities",
            "professional and leadership experience",
            "volunteer experience",
            "volunteer work",
            "volunteering",
            "community service",
            "community involvement",
            "community engagement",
            "civic engagement",
            "service",
            "public service",
            "board service",
            "board memberships",
            "board positions",
            "boards and committees",
            "committee service",
            "advisory roles",
            "advisory board positions",
            "governance",
            "internships",
            "internship experience",
            "co-op experience",
            "cooperative education",
            "summer experience",
            "summer employment",
            "apprenticeships",
            "trainee positions",
            "student experience",
            "extracurricular experience",
            "military experience",
            "military service",
            "armed forces service",
            "active duty",
            "veteran experience",
            "professional service",
            "editorial service",
            "editorial roles",
            "editorial positions",
            "editorial board",
            "editorial board service",
            "journal editorships",
            "peer review",
            "peer review service",
            "reviewer",
            "reviewer service",
            "consulting",
            "consultancies",
            "consultancy roles",
            "external service",
            "university service",
            "departmental service",
            "institutional service",
            "committee memberships",
        ],
        "education": [
            "education",
            "educational background",
            "educational history",
            "educational qualifications",
            "academic background",
            "academic qualifications",
            "academic history",
            "academics",
            "degree",
            "degrees",
            "degrees earned",
            "academic credentials",
            "formal education",
            "higher education",
            "undergraduate education",
            "graduate education",
            "postgraduate education",
            "professional education",
            "university",
            "college",
            "coursework",
            "relevant coursework",
            "selected coursework",
            "course highlights",
            "study abroad",
            "international studies",
            "exchange programs",
            "dissertation",
            "thesis",
        ],
        "other": [
            "training",
            "professional training",
            "professional development",
            "trainings and workshops",
            "workshops",
            "seminars",
            "continuing education",
            "executive education",
            "continuing professional development",
            "cpd",
            "continuing medical education",
            "cme",
            "bootcamps",
            "career development",
            "learning and development",
            "certification",
            "certifications",
            "certificates",
            "professional certifications",
            "certifications and licenses",
            "licenses",
            "licensure",
            "professional licenses",
            "credentials",
            "professional credentials",
            "accreditations",
            "registrations",
            "board certifications",
            "compliance training",
            "security clearances",
            "clearances",
            "government clearances",

            "contact",
            "contact information",
            "personal details",
            "personal information",
            "personal data",
            "biographical information",
            "bio",
            "header",
            "summary",
            "professional summary",
            "career summary",
            "executive summary",
            "qualifications summary",
            "summary of qualifications",
            "summary of skills and experience",
            "profile",
            "professional profile",
            "career profile",
            "personal profile",
            "objective",
            "career objective",
            "professional objective",
            "about me",
            "about",
            "overview",
            "career overview",
            "introduction",
            "highlights",
            "career highlights",
            "key highlights",
            "value proposition",
            "executive brief",
            "mission statement",
            "skills",
            "skill set",
            "core skills",
            "core competencies",
            "competencies",
            "key skills",
            "key competencies",
            "technical skills",
            "technical competencies",
            "technical expertise",
            "technical proficiencies",
            "technology skills",
            "software skills",
            "hardware skills",
            "tools and technologies",
            "technologies",
            "programming languages",
            "programming skills",
            "coding skills",
            "development skills",
            "frameworks and libraries",
            "platforms",
            "systems",
            "databases",
            "development tools",
            "analytical skills",
            "quantitative skills",
            "statistical skills",
            "data skills",
            "data analysis",
            "data science skills",
            "research skills",
            "laboratory skills",
            "lab techniques",
            "clinical skills",
            "soft skills",
            "interpersonal skills",
            "transferable skills",
            "personal skills",
            "professional skills",
            "managerial skills",
            "leadership skills",
            "communication skills",
            "presentation skills",
            "writing skills",
            "editorial skills",
            "language skills",
            "creative skills",
            "design skills",
            "additional skills",
            "other skills",
            "miscellaneous skills",
            "areas of expertise",
            "expertise",
            "specializations",
            "specialties",
            "domains of expertise",
            "functional expertise",
            "industry expertise",
            "strengths",
            "highlights of qualifications",
            "publications",
            "publication",
            "publication list",
            "peer-reviewed publications",
            "refereed publications",
            "journal articles",
            "journal publications",
            "peer-reviewed articles",
            "book chapters",
            "books",
            "authored books",
            "edited volumes",
            "manuscripts",
            "manuscripts in preparation",
            "manuscripts under review",
            "preprints",
            "working papers",
            "white papers",
            "technical reports",
            "reports",
            "book reviews",
            "editorials",
            "op-eds",
            "media contributions",
            "media coverage",
            "selected publications",
            "recent publications",
            "publications and presentations",
            "presentations",
            "presentation",
            "talks",
            "invited talks",
            "invited lectures",
            "invited presentations",
            "keynote presentations",
            "keynote addresses",
            "keynotes",
            "conference presentations",
            "conference talks",
            "conference proceedings",
            "poster presentations",
            "oral presentations",
            "selected presentations",
            "guest lectures",
            "public lectures",
            "speaking engagements",
            "panel discussions",
            "panels",
            "symposia",
            "workshops presented",
            "media appearances",
            "radio and podcast appearances",
            "grants",
            "grant funding",
            "research funding",
            "funding",
            "funded research",
            "sponsored research",
            "grants and awards",
            "grants received",
            "fellowships and grants",
            "contracts",
            "awarded contracts",
            "external funding",
            "internal funding",
            "awards",
            "honors",
            "honors and awards",
            "awards and honors",
            "awards and recognition",
            "achievements",
            "achievements and awards",
            "accomplishments",
            "recognitions",
            "distinctions",
            "scholarships",
            "fellowships and scholarships",
            "prizes",
            "nominations",
            "academic honors",
            "academic awards",
            "professional honors",
            "professional recognition",
            "selected honors",
            "notable achievements",
            "career achievements",
            "key achievements",
            "projects",
            "personal projects",
            "side projects",
            "professional projects",
            "selected projects",
            "key projects",
            "featured projects",
            "notable projects",
            "recent projects",
            "portfolio",
            "portfolio highlights",
            "case studies",
            "product portfolio",
            "academic projects",
            "research projects",
            "capstone projects",
            "independent projects",
            "software projects",
            "development projects",
            "open source",
            "open source contributions",
            "contributions",
            "professional affiliations",
            "affiliations",
            "professional memberships",
            "memberships",
            "society memberships",
            "association memberships",
            "professional organizations",
            "professional associations",
            "societies",
            "learned societies",
            "networks",
            "professional networks",
            "languages",
            "language proficiency",
            "foreign languages",
            "spoken languages",
            "fluencies",
            "multilingual skills",
            "interests",
            "personal interests",
            "hobbies",
            "hobbies and interests",
            "extracurricular interests",
            "extracurricular activities",
            "activities",
            "activities and interests",
            "passions",
            "outside interests",
            "volunteer interests",
            "references",
            "professional references",
            "academic references",
            "references available upon request",
            "referees",
            "nationality",
            "citizenship",
            "date of birth",
            "marital status",
            "photograph",
            "id",
            "identity",
            "curriculum vitae",
            "career path",
            "achievements and recognition",
            "professional synopsis",
            "career snapshot",
            "areas of interest",
            "personal vitae",
            "bio-data",
            "portfolio samples",
            "selected works",
            "works",
            "exhibitions",
            "solo exhibitions",
            "group exhibitions",
            "curatorial work",
            "performances",
            "selected performances",
            "repertoire",
            "discography",
            "filmography",
            "commissions",
            "residencies",
            "artist statement",
            "reviews",
            "press",
            "press coverage",
            "screenings",
            "technical projects",
            "technical portfolio",
            "github",
            "repositories",
            "coding challenges",
            "hackathons",
            "tech talks",
            "blog posts",
            "technical writing",
            "contributions to community",
            "vitae",
            "statement of purpose",
            "research statement",
            "teaching statement",
            "teaching philosophy",
            "diversity statement",
            "dei statement",
            "statement of contributions",
            "doctoral advisees",
            "postdoctoral advisees",
            "graduate students supervised",
            "undergraduate students supervised",
            "committees served",
            "thesis committees",
            "dissertation committees",
            "reading groups",
            "academic service",
            "reviewing service",
            "editorial boards served",
            "ad hoc reviewer",
            "symposia organized",
            "conferences organized",
            "executive profile",
            "executive highlights",
            "board experience",
            "board of directors",
            "corporate governance",
            "strategic leadership",
            "corporate boards",
            "financial highlights",
            "p&l ownership",
            "m&a experience",
            "turnaround experience",
            "growth highlights",
            "additional information",
            "additional details",
            "miscellaneous",
            "other",
            "notes",
            "appendix",
            "attachments",
            "supplemental information",
            "personal attributes",
            "characteristics",
            "career notes",
        ],
    }

    # Strip trailing "(cont.)" / "(continued)" from header lines
    CONT_RE = re.compile(r"\s*\((?:cont\.?|continued)\)\s*$", re.IGNORECASE)

    COMPANY_SUFFIXES = {
        "inc", "incorporated", "llc", "ltd", "limited", "corp", "corporation",
        "co", "company", "group", "holdings", "gmbh", "sa", "ag", "bv", "nv",
        "plc", "spa", "kk", "pte", "pvt", "partners", "associates",
    }

    _CANONICAL_KEYWORD_TO_SECTION: Dict[str, str] = {}
    
    @staticmethod
    def _normalize_header_text(text: str) -> str:
        
        text = re.sub(
            r'\b(?:[A-Za-z]\s+){2,}[A-Za-z]\b',
            lambda m: m.group(0).replace(" ", ""),
            text,
        )

        text = re.sub(r"[^A-Za-z0-9']", " ", text)
        text = re.sub(r"\s+", " ", text)

        return text.strip()


    @staticmethod
    def _canonical(value: str) -> str:
        """
        Reduce to lowercase-alphanumeric-only form.
        """
        if not value:
            return ""
        
        cleaned = SectionParser._normalize_header_text(value)
        cleaned = SectionParser.CONT_RE.sub("", value)
        cleaned = cleaned.lower()
        return re.sub(r"[^a-z0-9]+", "", cleaned)
    
    
    @staticmethod
    def _get_canonical_lookup() -> Dict[str, str]:
        """Lazy-build canonical-keyword → section-name map, cached."""
        if not SectionParser._CANONICAL_KEYWORD_TO_SECTION:
            lookup: Dict[str, str] = {}
            for section_name, keywords in SectionParser.SECTION_KEYWORDS.items():
                for kw in keywords:
                    lookup[SectionParser._canonical(kw)] = section_name
            SectionParser._CANONICAL_KEYWORD_TO_SECTION = lookup
        return SectionParser._CANONICAL_KEYWORD_TO_SECTION

    # ADDING WORD RATIO

    @staticmethod
    def _word_ratio_match(line: str) -> Optional:
        """
        Return the section name if any SECTION_KEYWORDS phrase appears in
        `line` as contiguous tokens AND its word count is >= 50% of the
        line's word count. Longer keyword phrases are preferred.
        """
        #DEBUG 
        # line = SectionParser._normalize_header_text(line)

        # print("NORMALIZED:", repr(line))
        # print(
        #     "WORDS:",
        #     re.findall(r"[a-z0-9]+", line.lower())
        # )

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

        for kw, section in keyword_pairs:
            kw_words = re.findall(r"[a-z0-9]+", kw.lower())
            if not kw_words:
                continue
            kw_word_count = len(kw_words)

            if kw_word_count / line_word_count < 0.3:
                continue

            for i in range(line_word_count - kw_word_count + 1):
                if line_words[i:i + kw_word_count] == kw_words:
                    return section

        return None


    @staticmethod
    def _build_line_counts(text: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for raw in text.split("\n"):
            stripped = raw.strip()
            if not stripped:
                continue
            canon = SectionParser._canonical(stripped)
            if not canon:
                continue
            counts[canon] = counts.get(canon, 0) + 1
        return counts

    @staticmethod
    def is_section_header(line: str, line_counts: Dict[str, int]) -> bool:
        """
        A line is a section header if:
        1. It appears exactly once in the document, AND
        2. Either:
            a. Its canonical form matches a SECTION_KEYWORDS entry, OR
            b. A SECTION_KEYWORDS phrase makes up >= 50% of its words.
        """
        # if "education" in line.lower():
        #     print("\nDEBUG HEADER CHECK")
        #     print("RAW      :", repr(line))

        #     canon = SectionParser._canonical(line)
        #     print("CANON    :", canon)

        #     lookup = SectionParser._get_canonical_lookup()
        #     print("IN LOOKUP:", canon in lookup)

        #     ratio = SectionParser._word_ratio_match(line)
        #     print("RATIO    :", ratio)

        #     print("COUNT    :", line_counts.get(canon))

        stripped = line.strip()
        if not stripped:
            return False
        if stripped.endswith(".") or len(stripped) > 120:
            return False

        canon = SectionParser._canonical(stripped)
        if not canon or len(canon) > 40:
            return False

        # Uniqueness gate — recurring lines are subsections, not sections
        if line_counts.get(canon, 0) != 1:
            return False

        # 1. Direct keyword match
        lookup = SectionParser._get_canonical_lookup()
        if canon in lookup:
            return True

        # 2. Word-ratio match — keyword phrase >= 50% of the line's words
        if SectionParser._word_ratio_match(stripped) is not None:
            return True

        return False



    @staticmethod
    def match_section_key(line: str, line_counts: Dict[str, int]) -> Optional:
        if not SectionParser.is_section_header(line, line_counts):
            return None

        canon = SectionParser._canonical(line.strip())
        lookup = SectionParser._get_canonical_lookup()

        if canon in lookup:
            return lookup[canon]

        return SectionParser._word_ratio_match(line.strip())



    @staticmethod
    def _looks_like_header_shape(line: str) -> bool:
        stripped = line.strip()
        if not stripped or stripped.endswith("."):
            return False
        if len(stripped) > 60:
            return False

        core = re.sub(r"[^A-Za-z0-9 ]+", "", stripped).strip()
        if not core or len(core) < 6:
            return False
        if any(ch.isdigit() for ch in core):
            return False

        letters = [c for c in core if c.isalpha()]
        if not letters:
            return False
        if sum(1 for c in letters if c.isupper()) / len(letters) < 0.8:
            return False

        words = core.split()
        if len(words) < 2:
            return False
        if words[-1].lower() in SectionParser.COMPANY_SUFFIXES:
            return False
        return True

    @staticmethod
    def _save_section(sections: Dict[str, str], key: str, content_lines: List[str]) -> None:
        content = "\n".join(content_lines).strip()
        if not content:
            return
        if key in sections:
            sections[key] = sections[key] + "\n" + content
        else:
            sections[key] = content


    @staticmethod
    def find_sections(text: str) -> Dict[str, str]:
        lines = text.split("\n")
        line_counts = SectionParser._build_line_counts(text)
        sections: Dict[str, str] = {}
        current_section = "header"
        current_content: List[str] = []

        for line in lines:
            if SectionParser.is_section_header(line, line_counts):
                # Split — known headers get their canonical bucket,
                # unknown-but-header-shaped ones get a synthetic bucket
                # so downstream code can still see them if it wants.
                key = SectionParser.match_section_key(line, line_counts) or "other"
                
                SectionParser._save_section(sections, current_section, current_content)
                current_section = key
                current_content = []
            else:
                if line.strip():
                    current_content.append(line)

        SectionParser._save_section(sections, current_section, current_content)
        return sections

