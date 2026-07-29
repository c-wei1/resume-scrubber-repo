#!/usr/bin/env python3
"""
benchmark_osd.py — Test detect_addresses.py against OpenStreetData country extracts.

OpenStreetData (https://openstreetdata.org/) publishes per-country TSV files:
    <CC>-streets.tsv.gz     streets with a name
    <CC>-houses.tsv.gz      house numbers + coords
    <CC>-addresses.tsv.gz   streets + house-number ranges + city/postcode

These are POSITIVE-ONLY corpora, so on their own they measure RECALL
(what fraction of real addresses your detector flags). Supply a file of
NEGATIVE (non-address) lines with --negatives to also get precision / F1.

Because the exact column order isn't formally documented and can vary by
file type, this script is schema-flexible:
  * Run with --peek to print the first rows (and any header) so you can see
    the layout, then map columns with --cols.
  * If you don't pass --cols, it tries to auto-detect house-number / street /
    city / postcode columns heuristically.

Typical usage
-------------
    # 1. Inspect the file layout
    python benchmark_osd.py BE-addresses.tsv.gz --peek

    # 2. Run the benchmark (auto column detection)
    python benchmark_osd.py BE-addresses.tsv.gz

    # 3. Explicit column mapping (0-based indices) + negatives for precision
    python benchmark_osd.py BE-addresses.tsv.gz \
        --cols house=1,street=0,city=3,postcode=2 \
        --negatives resume_negatives.txt \
        --sample 5000 --context

You can pass several country files at once for a per-country report:
    python benchmark_osd.py BE-addresses.tsv.gz FR-addresses.tsv.gz IN-houses.tsv.gz

Or point it at a WHOLE FOLDER (runs every .tsv/.tsv.gz inside):
    python benchmark_osd.py addresses/
    python benchmark_osd.py addresses/ --recursive --negatives resume_negatives.txt
    python benchmark_osd.py 'addresses/*-addresses.tsv.gz'   # glob also works
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import io
import os
import random
import re
import sys
from dataclasses import dataclass, field
from typing import Iterable, Optional

# ── Import the user's detector ────────────────────────────────────────────────
try:
    import address_identifier as det
except ImportError:
    sys.exit(
        "ERROR: could not import detect_addresses.py — run this script from the "
        "same directory as detect_addresses.py (or add it to PYTHONPATH)."
    )

# The detector must expose is_address_line(str) and/or redact_addresses(str).
_HAS_IS_LINE = hasattr(det, "is_address_line")
_HAS_REDACT = hasattr(det, "redact_addresses")
if not (_HAS_IS_LINE or _HAS_REDACT):
    sys.exit("ERROR: detect_addresses.py exposes neither is_address_line nor redact_addresses.")


# ── File reading helpers ──────────────────────────────────────────────────────
def _open_text(path: str) -> io.TextIOBase:
    """Open a plain or .gz TSV as UTF-8 text (ignoring undecodable bytes)."""
    if path.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8", errors="ignore")
    return open(path, "r", encoding="utf-8", errors="ignore")


def _sniff_rows(path: str, n: int) -> tuple[list[list[str]], bool]:
    """Return up to n rows (as token lists) and whether the first row looks like a header."""
    rows: list[list[str]] = []
    with _open_text(path) as fh:
        reader = csv.reader(fh, delimiter="\t")
        for i, row in enumerate(reader):
            rows.append(row)
            if i + 1 >= n:
                break
    header_like = False
    if rows:
        first = rows[0]
        # Header if the first row has no digits anywhere and later rows do.
        first_has_digit = any(any(ch.isdigit() for ch in c) for c in first)
        rest_has_digit = any(
            any(ch.isdigit() for ch in c) for r in rows[1:] for c in r
        )
        header_like = (not first_has_digit) and rest_has_digit
    return rows, header_like


# ── Column mapping ────────────────────────────────────────────────────────────
@dataclass
class ColMap:
    house: Optional[int] = None
    street: Optional[int] = None
    city: Optional[int] = None
    postcode: Optional[int] = None

    def any_set(self) -> bool:
        return any(v is not None for v in (self.house, self.street, self.city, self.postcode))


_POSTCODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{1,9}$")
_HOUSENUM_RE = re.compile(r"^\d{1,6}[A-Za-z]?(?:[/\-]\d{1,6}[A-Za-z]?)?$")


def _parse_colmap(spec: str) -> ColMap:
    cm = ColMap()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        key, _, val = part.partition("=")
        key = key.strip().lower()
        idx = int(val.strip())
        if key in ("house", "housenumber", "number", "num"):
            cm.house = idx
        elif key in ("street", "road", "streetname"):
            cm.street = idx
        elif key in ("city", "municipality", "town", "locality"):
            cm.city = idx
        elif key in ("postcode", "postal", "zip", "zipcode"):
            cm.postcode = idx
        else:
            raise ValueError(f"unknown column key '{key}'")
    return cm


def _auto_colmap(rows: list[list[str]], header_like: bool) -> ColMap:
    """Best-effort heuristic column detection from sampled data rows."""
    data = rows[1:] if header_like else rows
    if not data:
        return ColMap()
    ncols = max(len(r) for r in data)
    cm = ColMap()

    def col_values(c: int) -> list[str]:
        return [r[c].strip() for r in data if len(r) > c and r[c].strip()]

    # If there is a header, try to match by name first.
    if header_like and rows:
        for i, name in enumerate(rows[0]):
            n = name.strip().lower()
            if cm.house is None and any(k in n for k in ("house", "number", "num")):
                cm.house = i
            elif cm.street is None and any(k in n for k in ("street", "road", "name")):
                cm.street = i
            elif cm.city is None and any(k in n for k in ("city", "municip", "town", "local")):
                cm.city = i
            elif cm.postcode is None and any(k in n for k in ("post", "zip")):
                cm.postcode = i

    # Fill gaps heuristically from the data distribution.
    for c in range(ncols):
        vals = col_values(c)
        if not vals:
            continue
        housenum_ratio = sum(bool(_HOUSENUM_RE.match(v)) for v in vals) / len(vals)
        postcode_ratio = sum(
            bool(_POSTCODE_RE.match(v)) and any(ch.isdigit() for ch in v) for v in vals
        ) / len(vals)
        alpha_ratio = sum(any(ch.isalpha() for ch in v) for v in vals) / len(vals)
        avg_len = sum(len(v) for v in vals) / len(vals)

        if cm.house is None and housenum_ratio > 0.6:
            cm.house = c
        elif cm.postcode is None and 0.5 < postcode_ratio and avg_len <= 8 and c != cm.house:
            cm.postcode = c

    # Street = longest mostly-alpha column not already claimed.
    if cm.street is None:
        best, best_len = None, 0.0
        for c in range(ncols):
            if c in (cm.house, cm.postcode):
                continue
            vals = col_values(c)
            if not vals:
                continue
            alpha_ratio = sum(any(ch.isalpha() for ch in v) for v in vals) / len(vals)
            avg_len = sum(len(v) for v in vals) / len(vals)
            if alpha_ratio > 0.7 and avg_len > best_len:
                best, best_len = c, avg_len
        cm.street = best

    # City = next-longest mostly-alpha column not already claimed.
    if cm.city is None:
        best, best_len = None, 0.0
        for c in range(ncols):
            if c in (cm.house, cm.postcode, cm.street):
                continue
            vals = col_values(c)
            if not vals:
                continue
            alpha_ratio = sum(any(ch.isalpha() for ch in v) for v in vals) / len(vals)
            avg_len = sum(len(v) for v in vals) / len(vals)
            if alpha_ratio > 0.7 and avg_len > best_len:
                best, best_len = c, avg_len
        cm.city = best

    return cm


# ── Address string construction ───────────────────────────────────────────────
def _clean(tok: str) -> str:
    return tok.strip().strip('"').strip()


def _build_address(row: list[str], cm: ColMap, country: str) -> Optional[str]:
    """Assemble a realistic one-line address from a data row using the column map."""
    def get(i: Optional[int]) -> str:
        if i is None or i >= len(row):
            return ""
        return _clean(row[i])

    house = get(cm.house)
    street = get(cm.street)
    city = get(cm.city)
    postcode = get(cm.postcode)

    # Require at least a street to be a plausible address line.
    if not street:
        return None

    line1 = f"{house} {street}".strip() if house else street
    line2 = " ".join(p for p in (postcode, city) if p).strip()
    parts = [p for p in (line1, line2, country) if p]
    return ", ".join(parts) if parts else None


def _to_block(addr: str) -> str:
    """Wrap a one-line address in a tiny multi-line block so context scoring can engage."""
    line1, _, rest = addr.partition(", ")
    return f"{line1}\n{rest}" if rest else addr


# ── Negatives ─────────────────────────────────────────────────────────────────
def _load_negatives(path: str) -> list[str]:
    lines: list[str] = []
    with _open_text(path) as fh:
        for ln in fh:
            ln = ln.strip()
            if ln:
                lines.append(ln)
    return lines


# ── Detection wrappers ────────────────────────────────────────────────────────
def _detect_line(text: str, use_context: bool) -> bool:
    """True if the detector flags `text` as containing an address."""
    if use_context and _HAS_REDACT:
        # A line is 'detected' if redaction changed/blanked it.
        redacted = det.redact_addresses(text)
        return redacted.strip() != text.strip()
    if _HAS_IS_LINE:
        # is_address_line works on a single line; take the strongest line in a block.
        return any(det.is_address_line(l) for l in text.splitlines() if l.strip())
    # Fall back to redact even without context.
    return det.redact_addresses(text).strip() != text.strip()


# ── Metrics ───────────────────────────────────────────────────────────────────
@dataclass
class Result:
    country: str
    n_pos: int = 0
    tp: int = 0            # positives correctly flagged
    n_neg: int = 0
    fp: int = 0            # negatives wrongly flagged
    misses: list[str] = field(default_factory=list)
    false_hits: list[str] = field(default_factory=list)

    @property
    def recall(self) -> Optional[float]:
        return self.tp / self.n_pos if self.n_pos else None

    @property
    def precision(self) -> Optional[float]:
        denom = self.tp + self.fp
        return self.tp / denom if denom else None

    @property
    def f1(self) -> Optional[float]:
        p, r = self.precision, self.recall
        if p is None or r is None or (p + r) == 0:
            return None
        return 2 * p * r / (p + r)


def _country_code(path: str) -> str:
    base = os.path.basename(path)
    m = re.match(r"([A-Za-z]{2})[-_]", base)
    return m.group(1).upper() if m else base.split(".")[0]


# ── Core evaluation ───────────────────────────────────────────────────────────
def evaluate_file(
    path: str,
    cm: Optional[ColMap],
    sample: int,
    use_context: bool,
    negatives: list[str],
    keep_examples: int,
    seed: int,
) -> Result:
    country = _country_code(path)
    rows, header_like = _sniff_rows(path, 200)
    if cm is None or not cm.any_set():
        cm = _auto_colmap(rows, header_like)

    res = Result(country=country)
    rng = random.Random(seed)

    # Reservoir-sample `sample` data rows so we don't load the whole country.
    reservoir: list[list[str]] = []
    with _open_text(path) as fh:
        reader = csv.reader(fh, delimiter="\t")
        for i, row in enumerate(reader):
            if header_like and i == 0:
                continue
            idx = i - (1 if header_like else 0)
            if len(reservoir) < sample:
                reservoir.append(row)
            else:
                j = rng.randint(0, idx)
                if j < sample:
                    reservoir[j] = row

    for row in reservoir:
        addr = _build_address(row, cm, country)
        if not addr:
            continue
        res.n_pos += 1
        text = _to_block(addr) if use_context else addr
        if _detect_line(text, use_context):
            res.tp += 1
        elif len(res.misses) < keep_examples:
            res.misses.append(addr)

    # Negatives (shared across countries; counted per file for a full report).
    if negatives:
        neg_sample = negatives if len(negatives) <= sample else rng.sample(negatives, sample)
        for line in neg_sample:
            res.n_neg += 1
            if _detect_line(line, use_context):
                res.fp += 1
                if len(res.false_hits) < keep_examples:
                    res.false_hits.append(line)

    res._colmap = cm  # type: ignore[attr-defined]
    return res


# ── Reporting ─────────────────────────────────────────────────────────────────
def _fmt(x: Optional[float]) -> str:
    return f"{x*100:6.2f}%" if x is not None else "   n/a"


def print_report(results: list[Result], show_examples: int) -> None:
    print("\n" + "=" * 74)
    print(f"{'Country':<8}{'#Pos':>7}{'Recall':>10}{'#Neg':>7}{'Precision':>11}{'F1':>9}")
    print("-" * 74)
    tot = Result(country="ALL")
    for r in results:
        tot.n_pos += r.n_pos; tot.tp += r.tp
        tot.n_neg += r.n_neg; tot.fp += r.fp
        print(f"{r.country:<8}{r.n_pos:>7}{_fmt(r.recall):>10}"
              f"{r.n_neg:>7}{_fmt(r.precision):>11}{_fmt(r.f1):>9}")
    print("-" * 74)
    print(f"{tot.country:<8}{tot.n_pos:>7}{_fmt(tot.recall):>10}"
          f"{tot.n_neg:>7}{_fmt(tot.precision):>11}{_fmt(tot.f1):>9}")
    print("=" * 74)

    if show_examples:
        for r in results:
            cm = getattr(r, "_colmap", None)
            print(f"\n[{r.country}] column map used: house={cm.house} street={cm.street} "
                  f"city={cm.city} postcode={cm.postcode}"
                  if cm else f"\n[{r.country}]")
            if r.misses:
                print(f"  MISSED addresses (false negatives), up to {show_examples}:")
                for m in r.misses[:show_examples]:
                    print(f"    - {m}")
            if r.false_hits:
                print(f"  FALSE POSITIVES (negatives flagged), up to {show_examples}:")
                for f in r.false_hits[:show_examples]:
                    print(f"    - {f}")


# ── Peek mode ─────────────────────────────────────────────────────────────────
def do_peek(path: str, n: int) -> None:
    rows, header_like = _sniff_rows(path, n)
    print(f"\nFile: {path}")
    print(f"Header row detected: {header_like}")
    cm = _auto_colmap(rows, header_like)
    print(f"Auto-detected columns -> house={cm.house} street={cm.street} "
          f"city={cm.city} postcode={cm.postcode}")
    print("-" * 74)
    for i, row in enumerate(rows[:n]):
        cells = " | ".join(f"[{j}] {c}" for j, c in enumerate(row))
        tag = "  (header?)" if (header_like and i == 0) else ""
        print(f"row {i}{tag}: {cells}")
    print("-" * 74)
    print("Map columns explicitly with e.g. --cols house=1,street=0,city=3,postcode=2")


# ── Path expansion (files, folders, globs) ────────────────────────────────────
_TSV_EXTS = (".tsv.gz", ".tsv", ".txt.gz", ".txt")


def _looks_like_tsv(path: str) -> bool:
    return path.lower().endswith(_TSV_EXTS)


def expand_paths(paths: Iterable[str], recursive: bool = False) -> list[str]:
    """
    Expand a mix of files, directories, and glob patterns into a sorted,
    de-duplicated list of TSV files.

      * A directory  -> every .tsv/.tsv.gz inside it (recursively if `recursive`).
      * A glob string -> all matching files (e.g. 'addresses/BE-*.gz').
      * A plain file  -> kept as-is.
    """
    collected: list[str] = []
    seen: set[str] = set()

    def _add(fp: str) -> None:
        real = os.path.normpath(fp)
        if real not in seen and os.path.isfile(real):
            seen.add(real)
            collected.append(real)

    for raw in paths:
        if os.path.isdir(raw):
            if recursive:
                for root, _dirs, names in os.walk(raw):
                    for name in names:
                        if _looks_like_tsv(name):
                            _add(os.path.join(root, name))
            else:
                for name in os.listdir(raw):
                    fp = os.path.join(raw, name)
                    if os.path.isfile(fp) and _looks_like_tsv(name):
                        _add(fp)
        elif any(ch in raw for ch in "*?[") or "**" in raw:
            for match in glob.glob(raw, recursive=True):
                if os.path.isfile(match) and _looks_like_tsv(match):
                    _add(match)
        else:
            # A named file: keep it even if the extension is unusual.
            _add(raw)

    # Sort by country-code / basename so the report reads alphabetically.
    collected.sort(key=lambda p: os.path.basename(p).lower())
    return collected


# ── CLI ───────────────────────────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(
        description="Benchmark detect_addresses.py on OpenStreetData country TSV extracts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument("files", nargs="+",
                   help="OpenStreetData .tsv/.tsv.gz files, a FOLDER of them, or a glob "
                        "pattern. A folder is expanded to every .tsv/.tsv.gz inside it.")
    p.add_argument("--recursive", "-r", action="store_true",
                   help="When a folder is given, also descend into sub-folders.")
    p.add_argument("--peek", action="store_true", help="Print first rows + auto column guess, then exit.")
    p.add_argument("--peek-rows", type=int, default=8, help="Rows to show in --peek mode (default 8).")
    p.add_argument("--cols", type=str, default=None,
                   help="Explicit column map, e.g. 'house=1,street=0,city=3,postcode=2' (0-based).")
    p.add_argument("--sample", type=int, default=5000,
                   help="Max positive rows sampled per file (default 5000).")
    p.add_argument("--negatives", type=str, default=None,
                   help="Path to a file of non-address lines (one per line) for precision/F1.")
    p.add_argument("--context", action="store_true",
                   help="Wrap addresses in a small block and use redact_addresses() context scoring.")
    p.add_argument("--examples", type=int, default=5,
                   help="How many miss / false-positive examples to print per file (default 5).")
    p.add_argument("--seed", type=int, default=42, help="Random seed (default 42).")
    args = p.parse_args(argv)

    files = expand_paths(args.files, recursive=args.recursive)
    if not files:
        print("No .tsv/.tsv.gz files found in the given path(s). "
              "Pass files, a folder, or a glob like 'addresses/*.tsv.gz'.")
        return
    print(f"Found {len(files)} file(s) to benchmark:")
    for f in files:
        print(f"  • {f}")

    if args.peek:
        for f in files:
            do_peek(f, args.peek_rows)
        return

    cm = _parse_colmap(args.cols) if args.cols else None
    negatives = _load_negatives(args.negatives) if args.negatives else []

    if args.context and not _HAS_REDACT:
        print("WARN: --context requested but redact_addresses() not found; using is_address_line().")

    results: list[Result] = []
    for f in files:
        results.append(
            evaluate_file(
                f, cm, args.sample, args.context, negatives, args.examples, args.seed
            )
        )

    if results:
        print_report(results, args.examples)
    else:
        print("No files evaluated.")


if __name__ == "__main__":
    main()
