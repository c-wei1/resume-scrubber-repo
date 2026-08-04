"""
Convert Quill HTML output into structured data suitable for .docx generation.

The frontend sends rich-text content as HTML from a Quill editor.
This module parses that HTML into a list of "paragraph" dicts, each containing:
  - runs: list of dicts with keys 'text', 'bold', 'italic', 'underline'
  - list_type: 'bullet', 'ordered', or None
"""

from html.parser import HTMLParser


class _QuillHTMLParser(HTMLParser):
    """Parse Quill-generated HTML into paragraph-level structures."""

    def __init__(self):
        super().__init__()
        self.paragraphs = []
        self._current_runs = []
        self._bold = False
        self._italic = False
        self._underline = False
        self._list_stack = []  # stack of 'bullet' | 'ordered'
        self._in_li = False
        self._ol_counter = 0

    def _flush_paragraph(self, list_type=None):
        if self._current_runs:
            self.paragraphs.append({
                'runs': list(self._current_runs),
                'list_type': list_type,
            })
            self._current_runs = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'strong' or tag == 'b':
            self._bold = True
        elif tag == 'em' or tag == 'i':
            self._italic = True
        elif tag == 'u':
            self._underline = True
        elif tag == 'ul':
            self._list_stack.append('bullet')
        elif tag == 'ol':
            self._list_stack.append('ordered')
            self._ol_counter = 0
        elif tag == 'li':
            self._in_li = True
            self._current_runs = []
            if self._list_stack and self._list_stack[-1] == 'ordered':
                self._ol_counter += 1
        elif tag == 'p':
            self._current_runs = []
        elif tag == 'br':
            self._current_runs.append({
                'text': '\n',
                'bold': self._bold,
                'italic': self._italic,
                'underline': self._underline,
            })

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'strong' or tag == 'b':
            self._bold = False
        elif tag == 'em' or tag == 'i':
            self._italic = False
        elif tag == 'u':
            self._underline = False
        elif tag == 'li':
            list_type = self._list_stack[-1] if self._list_stack else None
            self._flush_paragraph(list_type=list_type)
            self._in_li = False
        elif tag == 'ul' or tag == 'ol':
            if self._list_stack:
                self._list_stack.pop()
            self._ol_counter = 0
        elif tag == 'p':
            self._flush_paragraph(list_type=None)

    def handle_data(self, data):
        if not data:
            return
        self._current_runs.append({
            'text': data,
            'bold': self._bold,
            'italic': self._italic,
            'underline': self._underline,
        })


def parse_quill_html(html: str) -> list[dict]:
    """
    Parse Quill HTML into a list of paragraph dicts.

    Each dict has:
      - runs: list[dict] with keys text, bold, italic, underline
      - list_type: 'bullet' | 'ordered' | None

    Falls back to plain-text splitting if the input contains no HTML tags.
    """
    if not html or not html.strip():
        return []

    # If there are no HTML tags, treat as plain text
    if '<' not in html:
        lines = [l for l in html.splitlines() if l.strip()]
        return [
            {'runs': [{'text': line, 'bold': False, 'italic': False, 'underline': False}], 'list_type': None}
            for line in lines
        ]

    parser = _QuillHTMLParser()
    parser.feed(html)
    # Flush any remaining content
    if parser._current_runs:
        parser._flush_paragraph()

    # Filter out empty paragraphs
    result = []
    for para in parser.paragraphs:
        combined = ''.join(r['text'] for r in para['runs']).strip()
        if combined:
            result.append(para)

    return result


def paragraphs_to_plain_lines(paragraphs: list[dict]) -> list[str]:
    """
    Convert parsed paragraphs back to plain-text lines with bullet prefixes.
    Useful for backends that only support plain text.
    """
    lines = []
    ol_counter = 0
    for para in paragraphs:
        text = ''.join(r['text'] for r in para['runs']).strip()
        if para['list_type'] == 'bullet':
            if not text.startswith('\u2022'):
                text = f'\u2022 {text}'
            ol_counter = 0
        elif para['list_type'] == 'ordered':
            ol_counter += 1
            text = f'{ol_counter}. {text}'
        else:
            ol_counter = 0
        lines.append(text)
    return lines
