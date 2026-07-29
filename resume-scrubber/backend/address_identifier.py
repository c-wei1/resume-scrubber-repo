"""
detect_addresses.py
Multi-stage address detection and redaction for plain-text strings.

International:
    * Multilingual street types: English suffixes, Romance/Slavic street
      *prefixes* (rue/via/calle/ulica ...), and fused Germanic/Scandinavian
      suffixes (…straat/…straße/…weg/…gata/…vej ...).
    * Postal codes for many formats (4/5/6-digit, alphanumeric UK/CA/NL,
      hyphenated BR/PL/PT/JP, country-prefixed CH-1010 ...), with precision
      guards so plain prose numbers ("25000 servers", "2016 Bachelor") don't
      trip the detector.
    * House number may appear before OR after the street name.

"""

# TODO: consider having international workers use the template? the identifier fails on addresses that are in a different language


from __future__ import annotations

import re
from typing import NamedTuple

# Unicode letter helpers (approximate, no external `regex` module needed)
_U_UP = r"A-ZÀ-ÖØ-Þ"          # uppercase incl. common Latin-1 accents
_U_LO = r"a-zà-öø-ÿ"          # lowercase incl. common Latin-1 accents
_U_AL = _U_UP + _U_LO


# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 · Postal / ZIP codes
# ──────────────────────────────────────────────────────────────────────────────
# "Strong" = distinctive enough to count on their own signal.
# Numeric codes carry a negative-lookahead so a number immediately followed by a
# lowercase word (e.g. "25000 servers") is NOT treated as a postcode.
_NOT_PROSE = r"(?!\s+[a-z])"

_PC_UK = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b", re.IGNORECASE)
_PC_CA = re.compile(r"\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b", re.IGNORECASE)
_PC_NL = re.compile(r"\b\d{4}\s?[A-Z]{2}\b")                      # 1011 AB
_PC_PREFIX = re.compile(r"\b[A-Z]{1,2}-\d{4,6}\b")               # CH-1010, AD-500
_PC_HYPHEN = re.compile(r"\b\d{4,5}-\d{3}\b" + _NOT_PROSE)       # BR/PL/PT/JP-ish
_PC_JP = re.compile(r"\b\d{3}-\d{4}\b" + _NOT_PROSE)
_PC_US5 = re.compile(r"\b\d{5}(?:-\d{4})?\b" + _NOT_PROSE)       # 94103 / 94103-1234
_PC_6 = re.compile(r"(?<!\d)\d{6}(?!\d)\b" + _NOT_PROSE)         # IN / CN / RU

_STRONG_PC = (_PC_UK, _PC_CA, _PC_NL, _PC_PREFIX, _PC_HYPHEN, _PC_JP, _PC_US5, _PC_6)

# "Weak" postal+locality: a 4-digit code (optionally country-prefixed) followed
# by a Capitalised locality — common in continental Europe ("7374 Gent",
# "1010 Lausanne"). Requires the following word to be capitalised so resume
# dates like "2016 Bachelor" score only weakly (and never alone reach THRESHOLD).
_PC_LOCALITY = re.compile(
    r"\b(?:[A-Z]{1,2}-)?\d{4}\b[ ,]+[" + _U_UP + r"][" + _U_AL + r".'\-]+",
)


def _has_strong_pc(line: str) -> bool:
    return any(rx.search(line) for rx in _STRONG_PC)


# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 · House / building number  (before OR after the street name)
# ──────────────────────────────────────────────────────────────────────────────
_HOUSE_NUM = re.compile(r"(?<!\d)\d{1,5}[A-Za-z]?(?:[/\-]\d{1,4}[A-Za-z]?)?\b")


# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 · Street types
# ──────────────────────────────────────────────────────────────────────────────
# (a) POST-name suffix words (English + Germanic/Scandinavian/Turkish standalone
#     forms). Matched as whole words, case-insensitive.
_SUFFIX_WORDS: frozenset[str] = frozenset({
    # English (full)
    "street", "avenue", "boulevard", "parkway", "expressway", "freeway",
    "highway", "terrace", "crescent", "circle", "square", "trail", "drive",
    "court", "place", "close", "grove", "mews", "lane", "road", "loop",
    "pass", "pike", "row", "run", "way", "walk", "gardens", "gate", "quay",
    "circus", "parade", "esplanade", "alley", "wharf", "heights", "rise",
    # English (abbrev)
    "st", "ave", "av", "blvd", "pkwy", "expy", "fwy", "hwy", "ter", "cres",
    "cir", "sq", "trl", "dr", "ct", "pl", "cl", "grv", "ln", "rd",
    # German / Dutch standalone  (note: "markt" is safe, "market" would collide
    # with common English resume words like "market analysis"/"marketing")
    "strasse", "straße", "gasse", "platz", "allee", "ring", "weg", "laan",
    "plein", "dreef", "steenweg", "kaai", "hof", "steeg", "markt", "marktplatz",
    "gracht", "singel", "kade",
    # Scandinavian standalone
    "gata", "gatan", "gate", "gaten", "vei", "veien", "vej", "gade", "plads",
    "torg", "vag", "väg", "vagen", "vägen", "katu", "tie", "ntie",
    # Turkish
    "sokak", "sok", "cadde", "caddesi", "bulvar", "bulvari", "meydan",
    # Misc transliterated
    "prospekt", "ulitsa", "pereulok", "rruga",
})
_SUFFIX_WORD_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in sorted(_SUFFIX_WORDS, key=len, reverse=True))
    + r")\.?\b",
    re.IGNORECASE,
)

# (b) PRE-name street types (Romance / Slavic / Malay ...). These double as
#     everyday words ("via", "rue"), so we require a following Capitalised name
#     or a number to count them — cuts false positives like "sent via email".
_STREET_PREFIXES: frozenset[str] = frozenset({
    "rue", "avenue", "av", "boulevard", "bd", "impasse", "quai", "chemin",
    "allee", "allées", "place", "cours",                       # French
    "via", "viale", "corso", "piazza", "piazzale", "vicolo", "largo", "strada",  # Italian
    "calle", "avenida", "avda", "paseo", "plaza", "camino", "carrer", "carrera",
    "carretera", "ronda", "passeig", "travesía", "glorieta",   # Spanish/Catalan
    "rua", "avenida", "praça", "praca", "alameda", "travessa", "largo", "estrada",  # Portuguese
    "ulica", "ul", "aleja", "plac", "osiedle",                 # Polish
    "jalan", "jln", "lorong", "gang",                          # Malay/Indonesian
    "odos", "leoforos", "plateia",                             # Greek (translit)
})
# Lowercase connector particles that legitimately follow a street type in
# Romance/Germanic names ("Rue de la Paix", "Piazza del Popolo", "Van der ...").
_CONNECTORS = (
    r"de|del|della|dello|dei|degli|delle|di|do|da|dos|das|du|des|d|"
    r"la|le|les|el|els|lo|los|las|l|van|von|der|den|ter|ten|op|aan"
)
# NOTE: the "next token" guard is wrapped in (?-i:...) so IGNORECASE on the
# prefix words does NOT leak into the character class (which previously let
# lowercase English words like "via port"/"via email" match a street prefix).
_STREET_PREFIX_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(s) for s in sorted(_STREET_PREFIXES, key=len, reverse=True))
    + r")\.?\b\s+(?:(?-i:[" + _U_UP + r"0-9])|(?:" + _CONNECTORS + r")\b)",
    re.IGNORECASE,
)

# (c) FUSED suffixes — the street type is glued onto the name
#     (Kerkstraat, Marktstraße, Brusselsesteenweg, Storgata, Mannerheimintie).
#     Require the token to be a proper noun (Titlecase or ALLCAPS) with a real
#     stem, so lowercase English words ("always", "brigade") don't match.
_FUSED = [
    "straat", "strasse", "straße", "gasse", "platz", "allee", "weg", "laan",
    "plein", "steenweg", "gata", "gatan", "gaten", "vägen", "vagen", "veien",
    "vei", "vej", "gade", "katu", "ntie", "vägen",
]
_FUSED_ALT = "|".join(sorted(set(_FUSED), key=len, reverse=True))
# Titlecase / mixed-case stem + lowercase fused suffix
_FUSED_RE = re.compile(
    r"\b[" + _U_UP + r"][" + _U_AL + r"]{2,}(?:" + _FUSED_ALT + r")\b"
)
# ALLCAPS variant
_FUSED_CAPS_RE = re.compile(
    r"\b[" + _U_UP + r"]{3,}(?:" + _FUSED_ALT.upper() + r")\b"
)


def _has_suffix(line: str) -> bool:
    return bool(
        _SUFFIX_WORD_RE.search(line)
        or _STREET_PREFIX_RE.search(line)
        or _FUSED_RE.search(line)
        or _FUSED_CAPS_RE.search(line)
    )


# ──────────────────────────────────────────────────────────────────────────────
# Stage 1 · Region codes, units, directions, PO boxes, countries
# ──────────────────────────────────────────────────────────────────────────────
_US_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID",
    "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS",
    "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK",
    "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV",
    "WI", "WY", "DC",
}
_AU_STATES = {"NSW", "VIC", "QLD", "SA", "WA", "TAS", "ACT", "NT"}
_CA_PROV = {"ON", "QC", "BC", "AB", "MB", "SK", "NS", "NB", "NL", "PE", "YT", "NT", "NU"}
_REGION_RE = re.compile(
    r"\b(" + "|".join(sorted(_US_STATES | _AU_STATES | _CA_PROV)) + r")\b"
)

_UNIT_RE = re.compile(
    r"\b(?:suite|ste|apt|apartment|unit|floor|fl|bldg|building|room|rm|#)\s*[\w\-]+",
    re.IGNORECASE,
)

_DIRECTION_RE = re.compile(r"\b(?:N|S|E|W|NE|NW|SE|SW)\.?\s", re.IGNORECASE)

_PO_BOX_RE = re.compile(
    r"\b(?:p\.?\s*o\.?\s*box|post\s*office\s*box|boîte\s*postale|postbus|casella\s*postale)\b",
    re.IGNORECASE,
)

# Full country names + a few unambiguous abbreviations (deliberately excludes
# 2-letter codes like "IT"/"IN" that collide with common words).
_COUNTRY_RE = re.compile(
    r"\b(?:USA|U\.S\.A\.|United\s+States|United\s+Kingdom|Deutschland|Germany|"
    r"France|España|Espana|Spain|Italia|Italy|Nederland|Netherlands|België|"
    r"Belgie|Belgium|Belgique|Schweiz|Suisse|Switzerland|Österreich|Austria|"
    r"Norge|Norway|Sverige|Sweden|Danmark|Denmark|Suomi|Finland|Polska|Poland|"
    r"Portugal|Brasil|Brazil|México|Mexico|Australia|India|Canada|Ireland|"
    r"Türkiye|Turkey|Ελλάδα|Greece)\b",
    re.IGNORECASE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Stage 2 · Scoring engine
# ──────────────────────────────────────────────────────────────────────────────
class _Signals(NamedTuple):
    has_house_num: bool
    has_suffix: bool
    has_strong_pc: bool
    has_weak_pc: bool
    has_region: bool
    has_unit: bool
    has_direction: bool
    has_po_box: bool
    has_country: bool


def _signals(line: str) -> _Signals:
    return _Signals(
        has_house_num=bool(_HOUSE_NUM.search(line)),
        has_suffix=_has_suffix(line),
        has_strong_pc=_has_strong_pc(line),
        has_weak_pc=bool(_PC_LOCALITY.search(line)),
        has_region=bool(_REGION_RE.search(line)),
        has_unit=bool(_UNIT_RE.search(line)),
        has_direction=bool(_DIRECTION_RE.search(line)),
        has_po_box=bool(_PO_BOX_RE.search(line)),
        has_country=bool(_COUNTRY_RE.search(line)),
    )


def _score(sig: _Signals) -> int:
    return (
        2 * sig.has_house_num
        + 3 * sig.has_suffix
        + 3 * sig.has_strong_pc
        + 2 * sig.has_weak_pc
        + 2 * sig.has_region
        + 1 * sig.has_unit
        + 1 * sig.has_direction
        + 3 * sig.has_po_box
        + 1 * sig.has_country
    )


def _score_line(line: str) -> int:
    return _score(_signals(line))


def _score_with_context(lines: list[str], idx: int) -> int:
    """Score lines[idx]; boost when neighbours also carry address signals."""
    base = _score_line(lines[idx])
    if base == 0:
        return 0
    for offset in (-1, 1):
        ni = idx + offset
        if 0 <= ni < len(lines) and _score_line(lines[ni]) > 0:
            base += 1
    return base


THRESHOLD = 5  # lines scoring at or above this are treated as addresses


def redact_addresses(text: str) -> str:
    """
    Remove address lines from *text* and return the cleaned string.

    Two passes:
      1. Blank every line whose contextual score >= THRESHOLD.
      2. Also blank an adjacent line that carries partial address signals
         (postcode / locality / region / country) so multi-line address
         blocks — e.g. a street line followed by a "1010 Lausanne" line —
         are removed in full.
    """
    if not text or not text.strip():
        return text

    lines = text.splitlines(keepends=True)
    n = len(lines)
    base_scores = [_score_line(l) for l in lines]
    ctx_scores = [_score_with_context(lines, i) for i in range(n)]

    confirmed = [s >= THRESHOLD for s in ctx_scores]

    # Pass 2: pull in neighbouring partial-address lines.
    PARTIAL = 2  # weak_pc / region / country lines score ~2-3 on their own
    redact = list(confirmed)
    for i in range(n):
        if confirmed[i]:
            for ni in (i - 1, i + 1):
                if 0 <= ni < n and not confirmed[ni] and base_scores[ni] >= PARTIAL:
                    redact[ni] = True

    result: list[str] = []
    for line, drop in zip(lines, redact):
        if drop:
            result.append("\n" if line.endswith("\n") else "")
        else:
            result.append(line)
    return "".join(result)


def is_address_line(text: str) -> bool:
    """Return True if *text* is likely a standalone address line."""
    return _score_line(text.strip()) >= THRESHOLD
