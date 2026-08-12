"""
Inspect the Kaggle Resume-NER dataset — print sample entries grouped by label.

Usage:
    cd backend
    python inspect_dataset.py
    python inspect_dataset.py --label COMPANY --n 10
    python inspect_dataset.py --all-labels
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict

DATA_PATH = Path(__file__).resolve().parent / "data" / "train.json"


def load_raw(path: Path) -> list[dict]:
    with open(path, encoding="utf-8", errors="replace") as f:
        return json.load(f)


def extract_examples(data: list[dict], max_per_label: int = 5) -> dict[str, list[str]]:
    """Extract text spans grouped by label."""
    examples: dict[str, list[str]] = defaultdict(list)
    for item in data:
        text = item["text"]
        for ann in item.get("annotations", []):
            start, end, label = ann[0], ann[1], ann[2]
            if start < 0 or end > len(text) or start >= end:
                continue
            span_text = text[start:end].strip()
            if span_text and len(examples[label]) < max_per_label:
                examples[label].append(span_text)
    return examples


def print_label_stats(data: list[dict]):
    """Print label frequency counts."""
    counts: dict[str, int] = defaultdict(int)
    for item in data:
        for ann in item.get("annotations", []):
            counts[ann[2]] += 1

    print(f"\n{'Label':<20} {'Count':>8}")
    print("-" * 30)
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"{label:<20} {count:>8}")
    print(f"{'─' * 30}")
    print(f"{'TOTAL':<20} {sum(counts.values()):>8}")
    print(f"{'Unique labels':<20} {len(counts):>8}")


def print_examples(data: list[dict], label_filter: str | None = None, n: int = 5):
    """Print example spans for each label (or a specific label)."""
    examples = extract_examples(data, max_per_label=n)

    labels = sorted(examples.keys())
    if label_filter:
        labels = [l for l in labels if l.upper() == label_filter.upper()]
        if not labels:
            print(f"Label '{label_filter}' not found in dataset.")
            return

    for label in labels:
        print(f"\n{'═' * 60}")
        print(f"  {label}  ({len(examples[label])} samples shown)")
        print(f"{'═' * 60}")
        for i, span in enumerate(examples[label], 1):
            # Truncate very long spans
            display = span[:120] + "..." if len(span) > 120 else span
            display = display.replace("\n", " ↵ ")
            print(f"  {i}. {display}")


def print_context_examples(data: list[dict], label_filter: str, n: int = 3):
    """Print spans WITH surrounding context to show annotation style."""
    print(f"\n{'═' * 60}")
    print(f"  {label_filter} — WITH CONTEXT (±50 chars)")
    print(f"{'═' * 60}")

    count = 0
    for item in data:
        if count >= n:
            break
        text = item["text"]
        for ann in item.get("annotations", []):
            if count >= n:
                break
            start, end, label = ann[0], ann[1], ann[2]
            if label.upper() != label_filter.upper():
                continue
            if start < 0 or end > len(text) or start >= end:
                continue

            span = text[start:end].strip()
            if not span:
                continue

            # Get context
            ctx_start = max(0, start - 50)
            ctx_end = min(len(text), end + 50)
            before = text[ctx_start:start].replace("\n", " ↵ ")
            after = text[end:ctx_end].replace("\n", " ↵ ")
            entity = text[start:end].replace("\n", " ↵ ")

            print(f"\n  Example {count + 1}:")
            print(f"    ...{before}[[[{entity}]]]{after}...")
            print(f"    Span: chars {start}–{end} ({end - start} chars)")
            count += 1


def main():
    parser = argparse.ArgumentParser(description="Inspect Kaggle Resume-NER dataset")
    parser.add_argument("--label", type=str, default=None,
                        help="Show examples for a specific label only")
    parser.add_argument("--n", type=int, default=5,
                        help="Number of examples per label (default: 5)")
    parser.add_argument("--all-labels", action="store_true",
                        help="Just print label frequency stats")
    parser.add_argument("--context", action="store_true",
                        help="Show spans with surrounding context")
    args = parser.parse_args()

    print(f"Loading {DATA_PATH} ...")
    data = load_raw(DATA_PATH)
    print(f"  {len(data)} entries loaded")

    if args.all_labels:
        print_label_stats(data)
        return

    if args.context and args.label:
        print_context_examples(data, args.label, n=args.n)
    else:
        print_examples(data, label_filter=args.label, n=args.n)


if __name__ == "__main__":
    main()
