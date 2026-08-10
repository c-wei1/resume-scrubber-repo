"""Tests for html_to_docx.py — Quill HTML parsing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from html_to_docx import paragraphs_to_plain_lines, parse_quill_html


# ═══════════════════════════════════════════════════════════════════════
# parse_quill_html
# ═══════════════════════════════════════════════════════════════════════
class TestParseQuillHTML:
    def test_empty_input(self):
        assert parse_quill_html("") == []
        assert parse_quill_html("   ") == []
        assert parse_quill_html(None) == []

    def test_plain_text_fallback(self):
        result = parse_quill_html("Line one\nLine two")
        assert len(result) == 2
        assert result[0]["runs"][0]["text"] == "Line one"
        assert result[1]["runs"][0]["text"] == "Line two"
        assert result[0]["list_type"] is None

    def test_simple_paragraph(self):
        result = parse_quill_html("<p>Hello world</p>")
        assert len(result) == 1
        assert result[0]["runs"][0]["text"] == "Hello world"
        assert result[0]["list_type"] is None

    def test_bold(self):
        result = parse_quill_html("<p><strong>Bold text</strong></p>")
        assert len(result) == 1
        assert result[0]["runs"][0]["bold"] is True
        assert result[0]["runs"][0]["text"] == "Bold text"

    def test_italic(self):
        result = parse_quill_html("<p><em>Italic text</em></p>")
        assert len(result) == 1
        assert result[0]["runs"][0]["italic"] is True

    def test_underline(self):
        result = parse_quill_html("<p><u>Underlined</u></p>")
        assert len(result) == 1
        assert result[0]["runs"][0]["underline"] is True

    def test_mixed_formatting(self):
        html = "<p>Normal <strong>bold</strong> <em>italic</em></p>"
        result = parse_quill_html(html)
        assert len(result) == 1
        runs = result[0]["runs"]
        assert any(r["bold"] for r in runs)
        assert any(r["italic"] for r in runs)

    def test_bullet_list(self):
        html = "<ul><li>Item A</li><li>Item B</li></ul>"
        result = parse_quill_html(html)
        assert len(result) == 2
        assert result[0]["list_type"] == "bullet"
        assert result[1]["list_type"] == "bullet"

    def test_ordered_list(self):
        html = "<ol><li>First</li><li>Second</li></ol>"
        result = parse_quill_html(html)
        assert len(result) == 2
        assert result[0]["list_type"] == "ordered"
        assert result[1]["list_type"] == "ordered"

    def test_empty_paragraphs_filtered(self):
        html = "<p>Real</p><p>   </p><p>Also real</p>"
        result = parse_quill_html(html)
        assert len(result) == 2

    def test_nested_bold_in_list(self):
        html = "<ul><li><strong>Bold bullet</strong></li></ul>"
        result = parse_quill_html(html)
        assert len(result) == 1
        assert result[0]["list_type"] == "bullet"
        assert result[0]["runs"][0]["bold"] is True


# ═══════════════════════════════════════════════════════════════════════
# paragraphs_to_plain_lines
# ═══════════════════════════════════════════════════════════════════════
class TestParagraphsToPlainLines:
    def test_plain_paragraphs(self):
        paras = [
            {"runs": [{"text": "Hello"}], "list_type": None},
            {"runs": [{"text": "World"}], "list_type": None},
        ]
        lines = paragraphs_to_plain_lines(paras)
        assert lines == ["Hello", "World"]

    def test_bullet_prefix(self):
        paras = [{"runs": [{"text": "Item"}], "list_type": "bullet"}]
        lines = paragraphs_to_plain_lines(paras)
        assert lines[0].startswith("\u2022")

    def test_ordered_prefix(self):
        paras = [
            {"runs": [{"text": "First"}], "list_type": "ordered"},
            {"runs": [{"text": "Second"}], "list_type": "ordered"},
        ]
        lines = paragraphs_to_plain_lines(paras)
        assert lines[0].startswith("1.")
        assert lines[1].startswith("2.")

    def test_counter_resets_on_non_list(self):
        paras = [
            {"runs": [{"text": "A"}], "list_type": "ordered"},
            {"runs": [{"text": "Break"}], "list_type": None},
            {"runs": [{"text": "B"}], "list_type": "ordered"},
        ]
        lines = paragraphs_to_plain_lines(paras)
        assert lines[2].startswith("1.")  # counter reset
