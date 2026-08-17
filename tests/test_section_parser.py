"""Tests for model_section_parser.py — header detection and section classification."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from model_section_parser import ModelSectionParser, _looks_like_header


# ═══════════════════════════════════════════════════════════════════════
# Header detection
# ═══════════════════════════════════════════════════════════════════════
class TestLooksLikeHeader:
    # Education headers
    def test_education_exact(self):
        assert _looks_like_header("Education") == "education"

    def test_education_uppercase(self):
        assert _looks_like_header("EDUCATION") == "education"

    def test_education_with_colon(self):
        assert _looks_like_header("Education:") == "education"

    def test_educational_background(self):
        assert _looks_like_header("Educational Background") == "education"

    def test_academic_background(self):
        assert _looks_like_header("Academic Background") == "education"

    # Experience headers
    def test_experience_exact(self):
        assert _looks_like_header("Experience") == "experience"

    def test_work_experience(self):
        assert _looks_like_header("Work Experience") == "experience"

    def test_professional_experience(self):
        assert _looks_like_header("Professional Experience") == "experience"

    def test_employment_history(self):
        assert _looks_like_header("Employment History") == "experience"

    def test_experience_uppercase(self):
        assert _looks_like_header("EXPERIENCE") == "experience"

    # Other section headers
    def test_skills(self):
        assert _looks_like_header("Skills") == "other"

    def test_certifications(self):
        assert _looks_like_header("Certifications") == "other"

    def test_summary(self):
        assert _looks_like_header("Summary") == "other"

    # Non-headers
    def test_long_line_not_header(self):
        assert _looks_like_header("A" * 50) is None

    def test_empty_not_header(self):
        assert _looks_like_header("") is None

    def test_plain_text_not_header(self):
        assert _looks_like_header("Responsible for managing a team of 10 engineers") is None

    def test_none_input(self):
        assert _looks_like_header(None) is None


# ═══════════════════════════════════════════════════════════════════════
# ModelSectionParser (header-only mode, no model)
# ═══════════════════════════════════════════════════════════════════════
class TestModelSectionParserHeaderOnly:
    """Test the parser with use_model=False (header-only fallback)."""

    def setup_method(self):
        self.parser = ModelSectionParser(use_model=False)

    def test_basic_resume_structure(self):
        pairs = [
            ("John Doe", None),
            ("Education", None),
            ("UCLA, B.S. Computer Science", None),
            ("Experience", None),
            ("Software Engineer at Company", None),
            ("Built features", None),
        ]
        sections = self.parser.find_sections(pairs)
        assert "education" in sections
        assert "experience" in sections

        edu_texts = [p[0] for p in sections["education"]]
        assert "UCLA, B.S. Computer Science" in edu_texts

        exp_texts = [p[0] for p in sections["experience"]]
        assert "Software Engineer at Company" in exp_texts
        assert "Built features" in exp_texts

    def test_excludes_header_line_by_default(self):
        pairs = [
            ("Education", None),
            ("UCLA", None),
        ]
        sections = self.parser.find_sections(pairs)
        edu_texts = [p[0] for p in sections["education"]]
        assert "Education" not in edu_texts
        assert "UCLA" in edu_texts

    def test_includes_header_when_configured(self):
        parser = ModelSectionParser(use_model=False, include_header_paragraph=True)
        pairs = [
            ("Education", None),
            ("UCLA", None),
        ]
        sections = parser.find_sections(pairs)
        edu_texts = [p[0] for p in sections["education"]]
        assert "Education" in edu_texts

    def test_preamble_excluded(self):
        """Text before any header should not appear in sections."""
        pairs = [
            ("John Doe", None),
            ("Summary of qualifications", None),
            ("Education", None),
            ("UCLA", None),
        ]
        sections = self.parser.find_sections(pairs)
        edu_texts = [p[0] for p in sections["education"]]
        exp_texts = [p[0] for p in sections["experience"]]
        assert "John Doe" not in edu_texts + exp_texts

    def test_other_section_excluded(self):
        """Content under 'Skills' should not leak into education/experience."""
        pairs = [
            ("Education", None),
            ("UCLA", None),
            ("Skills", None),
            ("Python, Java, SQL", None),
            ("Experience", None),
            ("Software Engineer", None),
        ]
        sections = self.parser.find_sections(pairs)
        edu_texts = [p[0] for p in sections["education"]]
        exp_texts = [p[0] for p in sections["experience"]]
        assert "Python, Java, SQL" not in edu_texts
        assert "Python, Java, SQL" not in exp_texts

    def test_empty_input(self):
        sections = self.parser.find_sections([])
        assert sections["education"] == []
        assert sections["experience"] == []

    def test_no_headers_returns_empty(self):
        """Without headers and without model, nothing is assigned."""
        pairs = [
            ("John Doe", None),
            ("UCLA, B.S. CS", None),
            ("Software Engineer", None),
        ]
        sections = self.parser.find_sections(pairs)
        assert sections["education"] == []
        assert sections["experience"] == []
