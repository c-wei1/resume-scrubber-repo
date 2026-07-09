"""
address_identifier.py
Multi-stage address detection and redaction for plain-text strings.

Pipeline
--------
1. Regex detectors  – house numbers, street suffixes, ZIP/postcodes, state codes
2. Scoring engine   – per-line confidence score, boosted by neighbouring lines
3. Redaction        – blank confirmed address lines; return cleaned text
"""

from __future__ import annotations

import re
from typing import NamedTuple

# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 · Regex primitives
# ──────────────────────────────────────────────────────────────────────────────

# ZIP / postcodes
_ZIP_US = re.compile(r'\b\d{5}(?:-\d{4})?\b')
_ZIP_CA = re.compile(r'\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b', re.IGNORECASE)
_ZIP_UK = re.compile(r'\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b', re.IGNORECASE)

# House / building number (up to 5 digits, optional letter suffix e.g. "12B")
_HOUSE_NUM = re.compile(r'(?<!\d)\d{1,5}[A-Za-z]?\b')

# Street suffix tokens – sorted longest-first so greedy alternation works
_SUFFIXES: frozenset[str] = frozenset({
    'street', 'avenue', 'boulevard', 'parkway', 'expressway', 'freeway',
    'highway', 'terrace', 'crescent', 'circle', 'square', 'trail',
    'drive', 'court', 'place', 'close', 'grove', 'mews', 'lane', 'road',
    'loop', 'pass', 'pike', 'row', 'run', 'way',
    'st', 'ave', 'blvd', 'pkwy', 'expy', 'fwy', 'hwy',
    'ter', 'cres', 'cir', 'sq', 'trl',
    'dr', 'ct', 'pl', 'cl', 'grv', 'ln', 'rd',
})

_SUFFIX_RE = re.compile(
    r'\b(?:' +
    '|'.join(re.escape(s) for s in sorted(_SUFFIXES, key=len, reverse=True)) +
    r')\.?\b',
    re.IGNORECASE,
)

# US state abbreviations
_US_STATES: frozenset[str] = frozenset({
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC',
})
_STATE_RE = re.compile(r'\b(' + '|'.join(_US_STATES) + r')\b')

# Directional prefixes: N., SW., NE, etc.
_DIRECTION_RE = re.compile(r'\b(?:N|S|E|W|NE|NW|SE|SW)\.?\s', re.IGNORECASE)

# Suite / unit designators
_UNIT_RE = re.compile(
    r'\b(?:suite|ste|apt|apartment|unit|floor|fl|#)\s*[\w\-]+',
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 · Scoring engine
# ──────────────────────────────────────────────────────────────────────────────

class _Signals(NamedTuple):
    has_house_num: bool
    has_suffix: bool
    has_zip: bool
    has_state: bool
    has_direction: bool
    has_unit: bool


def _signals(line: str) -> _Signals:
    return _Signals(
        has_house_num=bool(_HOUSE_NUM.search(line)),
        has_suffix=bool(_SUFFIX_RE.search(line)),
        has_zip=bool(
            _ZIP_US.search(line) or _ZIP_CA.search(line) or _ZIP_UK.search(line)
        ),
        has_state=bool(_STATE_RE.search(line)),
        has_direction=bool(_DIRECTION_RE.search(line)),
        has_unit=bool(_UNIT_RE.search(line)),
    )


def _score(sig: _Signals) -> int:
    return (
        2 * sig.has_house_num
        + 2 * sig.has_suffix
        + 3 * sig.has_zip
        + 2 * sig.has_state
        + 1 * sig.has_direction
        + 1 * sig.has_unit
    )


def _score_line(line: str) -> int:
    return _score(_signals(line))


def _score_with_context(lines: list[str], idx: int) -> int:
    """Score lines[idx]; add +1 for each adjacent line that also carries signals."""
    base = _score_line(lines[idx])
    if base == 0:
        return 0
    for offset in (-1, 1):
        ni = idx + offset
        if 0 <= ni < len(lines) and _score_line(lines[ni]) > 0:
            base += 1
    return base


THRESHOLD = 4  # lines scoring at or above this are treated as addresses


def redact_addresses(text: str) -> str:
    """
    Remove address lines from *text* and return the cleaned string.
    Processes line-by-line so neighbouring-line context is available.
    """
    if not text or not text.strip():
        return text

    lines = text.splitlines(keepends=True)
    scores = [_score_with_context(lines, i) for i in range(len(lines))]

    result: list[str] = []
    for line, score in zip(lines, scores):
        if score >= THRESHOLD:
            result.append('\n' if line.endswith('\n') else '')
        else:
            result.append(line)

    return ''.join(result)


def is_address_line(text: str) -> bool:
    """Return True if *text* is likely a standalone address line."""
    return _score_line(text.strip()) >= THRESHOLD
    return False
