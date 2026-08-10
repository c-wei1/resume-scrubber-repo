"""Tests for address_identifier.py — scoring, detection, and redaction."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from address_identifier import (
    THRESHOLD,
    _has_strong_pc,
    _has_suffix,
    _score_line,
    is_address_line,
    redact_addresses,
)


# ═══════════════════════════════════════════════════════════════════════
# Street suffix detection
# ═══════════════════════════════════════════════════════════════════════
class TestStreetSuffix:
    def test_english_street(self):
        assert _has_suffix("123 Main Street")

    def test_english_avenue(self):
        assert _has_suffix("456 Park Avenue")

    def test_english_blvd(self):
        assert _has_suffix("789 Sunset Blvd")

    def test_german_strasse(self):
        assert _has_suffix("Berlinerstraße")

    def test_french_prefix_rue(self):
        assert _has_suffix("Rue de la Paix")

    def test_no_street(self):
        assert not _has_suffix("Bachelor of Science")


# ═══════════════════════════════════════════════════════════════════════
# Postal code detection
# ═══════════════════════════════════════════════════════════════════════
class TestPostalCodes:
    def test_us_zip(self):
        assert _has_strong_pc("San Jose 95134")

    def test_us_zip_plus4(self):
        assert _has_strong_pc("94103-1234")

    def test_uk_postcode(self):
        assert _has_strong_pc("SW1A 1AA")

    def test_canadian_postcode(self):
        assert _has_strong_pc("K1A 0B1")

    def test_not_a_year(self):
        """A plain year like 2016 should NOT be treated as a postal code
        when followed by a lowercase word."""
        assert not _has_strong_pc("2016 bachelor")


# ═══════════════════════════════════════════════════════════════════════
# Line scoring
# ═══════════════════════════════════════════════════════════════════════
class TestScoring:
    def test_full_address_above_threshold(self):
        score = _score_line("123 Main Street, San Jose, CA 95134")
        assert score >= THRESHOLD

    def test_plain_text_below_threshold(self):
        score = _score_line("Proficient in Python and JavaScript")
        assert score < THRESHOLD

    def test_po_box(self):
        score = _score_line("P.O. Box 1234")
        assert score >= 3  # PO box alone = 3 pts

    def test_university_not_address(self):
        score = _score_line("University of California, Los Angeles")
        assert score < THRESHOLD


# ═══════════════════════════════════════════════════════════════════════
# is_address_line
# ═══════════════════════════════════════════════════════════════════════
class TestIsAddressLine:
    def test_full_us_address(self):
        assert is_address_line("123 Main Street, San Jose, CA 95134")

    def test_not_address(self):
        assert not is_address_line("Experienced software engineer")

    def test_not_address_education(self):
        assert not is_address_line("Bachelor of Science, Computer Science, 2020")

    def test_uk_address(self):
        assert is_address_line("10 Downing Street, London SW1A 2AA")

    def test_empty_string(self):
        assert not is_address_line("")


# ═══════════════════════════════════════════════════════════════════════
# redact_addresses
# ═══════════════════════════════════════════════════════════════════════
class TestRedactAddresses:
    def test_removes_address_line(self):
        text = "John Doe\n123 Main Street, San Jose, CA 95134\nSoftware Engineer"
        result = redact_addresses(text)
        assert "123 Main Street" not in result
        assert "John Doe" in result
        assert "Software Engineer" in result

    def test_preserves_non_address(self):
        text = "Skills: Python, JavaScript\nExperience: 5 years"
        result = redact_addresses(text)
        assert result == text

    def test_empty_input(self):
        assert redact_addresses("") == ""
        assert redact_addresses("   ") == "   "

    def test_multiline_address_block(self):
        text = "Name\n123 Oak Avenue\nSan Jose, CA 95134\nEducation"
        result = redact_addresses(text)
        assert "123 Oak Avenue" not in result
        assert "Name" in result
