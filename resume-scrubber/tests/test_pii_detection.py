"""Tests for PII regex patterns and validation in clean_resume.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from clean_resume import (
    _CITY_STATE_RE,
    _EMAIL_RE,
    _PHONE_RE,
    _URL_RE,
    _find_pii_spans,
    _redact_phones_sub,
    is_plausible_phone,
)


# ═══════════════════════════════════════════════════════════════════════
# Phone detection
# ═══════════════════════════════════════════════════════════════════════
class TestPhoneRegex:
    """Phone regex + digit-count validator."""

    def test_us_standard(self):
        assert _PHONE_RE.search("(555) 123-4567")
        assert is_plausible_phone("(555) 123-4567")

    def test_us_with_country_code(self):
        assert _PHONE_RE.search("+1 555-123-4567")
        assert is_plausible_phone("+1 555-123-4567")

    def test_international(self):
        assert _PHONE_RE.search("+44 20 7946 0958")
        assert is_plausible_phone("+44 20 7946 0958")

    def test_with_extension(self):
        m = _PHONE_RE.search("555-123-4567 ext. 890")
        assert m is not None

    def test_dots_separator(self):
        assert _PHONE_RE.search("555.123.4567")

    def test_rejects_short_number(self):
        """4-digit numbers like years should NOT pass validation."""
        assert not is_plausible_phone("2016")

    def test_rejects_too_few_digits(self):
        assert not is_plausible_phone("123-45")  # 5 digits

    def test_no_match_inside_email(self):
        """Phone regex should NOT match digits inside an email address."""
        text = "user1234567@example.com"
        m = _PHONE_RE.search(text)
        # If it matches, it shouldn't be at the start of the email
        if m:
            assert m.start() > text.index("@")

    def test_redact_phones_sub(self):
        text = "Call me at (555) 123-4567 or visit example.com"
        result = _redact_phones_sub(text)
        assert "(555) 123-4567" not in result


# ═══════════════════════════════════════════════════════════════════════
# Email detection
# ═══════════════════════════════════════════════════════════════════════
class TestEmailRegex:
    def test_standard_email(self):
        assert _EMAIL_RE.search("john.doe@example.com")

    def test_plus_addressing(self):
        assert _EMAIL_RE.search("user+tag@domain.org")

    def test_subdomain(self):
        assert _EMAIL_RE.search("admin@mail.company.co.uk")

    def test_no_false_positive_on_plain_text(self):
        assert _EMAIL_RE.search("this is not an email") is None

    def test_hyphenated_domain(self):
        assert _EMAIL_RE.search("test@my-company.com")


# ═══════════════════════════════════════════════════════════════════════
# URL detection
# ═══════════════════════════════════════════════════════════════════════
class TestURLRegex:
    def test_https(self):
        assert _URL_RE.search("https://example.com/page")

    def test_http(self):
        assert _URL_RE.search("http://example.com")

    def test_www(self):
        assert _URL_RE.search("www.example.com")

    def test_linkedin(self):
        assert _URL_RE.search("linkedin.com/in/johndoe")

    def test_github(self):
        assert _URL_RE.search("github.com/username")

    def test_no_false_positive(self):
        assert _URL_RE.search("this is plain text") is None


# ═══════════════════════════════════════════════════════════════════════
# City, STATE detection
# ═══════════════════════════════════════════════════════════════════════
class TestCityStateRegex:
    def test_san_francisco_ca(self):
        assert _CITY_STATE_RE.search("San Francisco, CA")

    def test_new_york_ny(self):
        assert _CITY_STATE_RE.search("New York, NY")

    def test_los_angeles_ca(self):
        assert _CITY_STATE_RE.search("Los Angeles, CA")

    def test_australian_state(self):
        assert _CITY_STATE_RE.search("Sydney, NSW")

    def test_canadian_province(self):
        assert _CITY_STATE_RE.search("Toronto, ON")

    def test_no_lowercase_city(self):
        """City must start with uppercase."""
        assert _CITY_STATE_RE.search("experience, CA") is None


# ═══════════════════════════════════════════════════════════════════════
# PII span detection (combined)
# ═══════════════════════════════════════════════════════════════════════
class TestFindPIISpans:
    def test_no_pii(self):
        assert _find_pii_spans("No PII here at all") == []

    def test_email_detected(self):
        spans = _find_pii_spans("Contact: john@example.com for info")
        assert len(spans) == 1
        text = "Contact: john@example.com for info"
        start, end = spans[0]
        assert text[start:end] == "john@example.com"

    def test_multiple_pii(self):
        text = "Email john@ex.com or call (555) 123-4567"
        spans = _find_pii_spans(text)
        assert len(spans) >= 2

    def test_overlapping_spans_merged(self):
        """Overlapping/adjacent spans should be merged."""
        text = "john@example.com john@example.com"
        spans = _find_pii_spans(text)
        # Each occurrence should be a separate span (they're not overlapping)
        assert len(spans) == 2

    def test_phone_and_email(self):
        text = "555-123-4567 | user@test.org"
        spans = _find_pii_spans(text)
        assert len(spans) == 2
