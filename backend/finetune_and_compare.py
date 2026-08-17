"""
Fine-tune en_core_web_md on the Kaggle Resume-NER dataset (backend/data/train.json)
and compare with the existing fine-tuned model (backend/resume_ner_model).

Usage:
    cd backend
    python finetune_and_compare.py            # 30 epochs (default)
    python finetune_and_compare.py --epochs 10  # faster run

The script will:
  1. Load & convert the Kaggle dataset into spaCy DocBin format
  2. Map the Kaggle labels to the labels used by the existing model
  3. Fine-tune a fresh en_core_web_md on an 80/20 train/dev split
  4. Save the new model to  backend/resume_ner_model_v2/
  5. Evaluate both models on the held-out dev set and print a comparison
"""

from __future__ import annotations

import argparse
import json
import math
import random
import warnings
from pathlib import Path

from tqdm import tqdm

import spacy
from spacy.tokens import DocBin
from spacy.training import Example
from spacy.util import minibatch, compounding

# ── Paths ─────────────────────────────────────────────────────
HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "data" / "train.json"
OLD_MODEL_PATH = HERE / "resume_ner_model"
NEW_MODEL_PATH = HERE / "resume_ner_model_v2"
BASE_MODEL = "en_core_web_md"

# ── Label mapping ─────────────────────────────────────────────
# Kaggle dataset labels  →  labels used by the existing pipeline
# (so both models share the same label vocabulary and are directly comparable).
LABEL_MAP: dict[str, str | None] = {
    "COMPANY":       "COMPANIES_WORKED_AT",
    "EDUCATION":     "DEGREE",              # closest match
    "EXPERIENCE":    "YEARS_OF_EXPERIENCE",
    "DESIGNATION":   "DESIGNATION",          # new label
    "SKILL":         "SKILL",               # new label
    "PERSON":        "PERSON",              # already in base model
    "LOCATION":      "GPE",                 # standard spaCy label
    "EMAIL":         "EMAIL",               # new label
    "CERTIFICATION": "CERTIFICATION",       # new label
    "LANGUAGE":      "LANGUAGE",            # already in base model
    "COLLABORATION": None,                  # drop — too noisy
    "ACTION":        None,                  # drop — too noisy
    "EXPERTISE":     "SKILL",               # merge with SKILL
    "OTHER":         None,                  # drop
}

# Labels to completely discard (too noisy / not useful)
DROP_LABELS = {"COLLABORATION", "ACTION", "OTHER"}

# Labels that survive (mapped or kept as-is)
def _map_label(lbl: str) -> str | None:
    if lbl in DROP_LABELS:
        return None
    mapped = LABEL_MAP.get(lbl, lbl)
    return mapped


# ── Helpers ────────────────────────────────────────────────────
# Some resume texts contain unpaired Unicode surrogates (e.g. \ud83d)
# which crash spaCy's tokenizer.  Strip them before training.
import re
_SURROGATE_RE = re.compile(r'[\ud800-\udfff]')

def _sanitize_text(text: str) -> str:
    """Remove unpaired surrogates and other non-encodable characters."""
    return _SURROGATE_RE.sub('', text)


# ── Load & convert dataset ────────────────────────────────────
def load_dataset(path: Path) -> list[tuple[str, dict]]:
    """Return list of (text, {"entities": [(start, end, label), ...]})."""
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = json.load(f)

    dataset: list[tuple[str, dict]] = []
    skipped = 0
    for item in raw:
        text = _sanitize_text(item["text"])
        entities: list[tuple[int, int, str]] = []
        for ann in item.get("annotations", []):
            start, end, label = ann[0], ann[1], ann[2]
            mapped = _map_label(label)
            if mapped is None:
                continue
            # Basic sanity: span must be within text bounds
            if start < 0 or end > len(text) or start >= end:
                continue
            # Strip leading/trailing whitespace from span (prevents E024 errors)
            while start < end and text[start] in (" ", "\t", "\n", "\r"):
                start += 1
            while end > start and text[end - 1] in (" ", "\t", "\n", "\r"):
                end -= 1
            if start >= end:
                continue
            entities.append((start, end, mapped))

        # Remove overlapping spans (keep longest)
        entities.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        clean: list[tuple[int, int, str]] = []
        last_end = 0
        for s, e, l in entities:
            if s >= last_end:
                clean.append((s, e, l))
                last_end = e

        if clean:
            dataset.append((text, {"entities": clean}))
        else:
            skipped += 1

    print(f"Loaded {len(dataset)} examples ({skipped} skipped — no entities after filtering)")
    return dataset


def make_docbin(nlp, data: list[tuple[str, dict]], out_path: Path) -> DocBin:
    """Convert (text, annotations) pairs to a spaCy DocBin."""
    db = DocBin()
    n_ok = 0
    for text, annot in data:
        doc = nlp.make_doc(text)
        ents = []
        for start, end, label in annot["entities"]:
            span = doc.char_span(start, end, label=label, alignment_mode="contract")
            if span is not None:
                ents.append(span)
        # Filter overlapping spans after char_span alignment
        filtered = spacy.util.filter_spans(ents)
        doc.ents = filtered
        db.add(doc)
        n_ok += 1
    db.to_disk(out_path)
    print(f"  Wrote {n_ok} docs → {out_path}")
    return db


# ── Training ──────────────────────────────────────────────────
def train_model(
    train_data: list[tuple[str, dict]],
    dev_data: list[tuple[str, dict]],
    output_dir: Path,
    n_iter: int = 30,
    drop: float = 0.3,
) -> spacy.Language:
    """Fine-tune en_core_web_md NER on the provided data."""
    print(f"\nLoading base model '{BASE_MODEL}' ...")
    nlp = spacy.load(BASE_MODEL)

    # Remove all pipes except tok2vec and ner for clean NER-only training
    pipes_to_remove = [p for p in nlp.pipe_names if p not in ("tok2vec", "ner")]
    for pipe_name in pipes_to_remove:
        nlp.remove_pipe(pipe_name)
    print(f"  Pipeline after cleanup: {nlp.pipe_names}")

    # Get the NER pipe and add new labels
    ner = nlp.get_pipe("ner")
    all_labels = set()
    for _, annot in train_data:
        for _, _, label in annot["entities"]:
            all_labels.add(label)
    for label in all_labels:
        ner.add_label(label)
    print(f"  NER labels ({len(ner.labels)}): {sorted(ner.labels)}")

    print(f"\nTraining for {n_iter} iterations on {len(train_data)} examples ...")
    best_f1 = 0.0

    # Estimate batch count for progress bar (compounding starts at 4, caps ~32)
    est_batches = max(1, math.ceil(len(train_data) / 16))  # rough avg batch size

    optimizer = nlp.resume_training()

    epoch_bar = tqdm(range(1, n_iter + 1), desc="Epochs", unit="epoch", position=0)
    for epoch in epoch_bar:
        random.shuffle(train_data)
        losses: dict[str, float] = {}
        batches = list(minibatch(train_data, size=compounding(4.0, 32.0, 1.001)))
        batch_count = 0

        batch_bar = tqdm(batches, desc=f"  Epoch {epoch:2d}", unit="batch",
                         leave=False, position=1)
        for batch in batch_bar:
            examples = []
            for text, annot in batch:
                doc = nlp.make_doc(text)
                example = Example.from_dict(doc, {"entities": annot["entities"]})
                examples.append(example)
            try:
                nlp.update(examples, sgd=optimizer, drop=drop, losses=losses)
                batch_count += 1
                batch_bar.set_postfix(loss=f"{losses.get('ner', 0):.1f}")
            except Exception:
                continue
        batch_bar.close()

        # Evaluate every 5 epochs or at the end
        if epoch % 5 == 0 or epoch == n_iter:
            scores = evaluate(nlp, dev_data)
            f1 = scores["ents_f"]
            epoch_bar.set_postfix(loss=f"{losses.get('ner', 0):.0f}",
                                 F1=f"{f1:.1f}", best=f"{best_f1:.1f}")
            tqdm.write(f"  Epoch {epoch:3d}  loss={losses.get('ner', 0):.2f}  "
                       f"P={scores['ents_p']:.1f}  R={scores['ents_r']:.1f}  F1={f1:.1f}"
                       f"  (batches: {batch_count})")

            # Save checkpoint every 5 epochs
            ckpt_dir = output_dir.parent / f"resume_ner_model_v2_epoch{epoch}"
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            nlp.to_disk(ckpt_dir)
            tqdm.write(f"         checkpoint → {ckpt_dir.name}/")

            # Also save as best model if F1 improved
            if f1 > best_f1:
                best_f1 = f1
                output_dir.mkdir(parents=True, exist_ok=True)
                nlp.to_disk(output_dir)
                tqdm.write(f"         ★ new best F1={f1:.1f} → {output_dir.name}/")
        else:
            epoch_bar.set_postfix(loss=f"{losses.get('ner', 0):.0f}",
                                 best=f"{best_f1:.1f}")

    print(f"\nBest dev F1: {best_f1:.1f} — saved to {output_dir}")
    return spacy.load(output_dir)


# ── Evaluation ────────────────────────────────────────────────
def evaluate(nlp: spacy.Language, data: list[tuple[str, dict]]) -> dict:
    """Evaluate NER on (text, annotations) pairs. Returns dict with ents_p/r/f."""
    examples = []
    for text, annot in data:
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annot)
        examples.append(example)
    scores = nlp.evaluate(examples)
    return {
        "ents_p": scores.get("ents_p", 0) * 100,
        "ents_r": scores.get("ents_r", 0) * 100,
        "ents_f": scores.get("ents_f", 0) * 100,
    }


def evaluate_per_label(nlp: spacy.Language, data: list[tuple[str, dict]]) -> dict[str, dict]:
    """Per-label P/R/F1."""
    from collections import defaultdict
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for text, annot in data:
        doc = nlp(text)
        pred_ents = {(e.start_char, e.end_char, e.label_) for e in doc.ents}
        gold_ents = {(s, e, l) for s, e, l in annot["entities"]}

        for ent in pred_ents:
            if ent in gold_ents:
                tp[ent[2]] += 1
            else:
                fp[ent[2]] += 1
        for ent in gold_ents:
            if ent not in pred_ents:
                fn[ent[2]] += 1

    results = {}
    all_labels = sorted(set(tp) | set(fp) | set(fn))
    for label in all_labels:
        p = tp[label] / (tp[label] + fp[label]) * 100 if (tp[label] + fp[label]) else 0
        r = tp[label] / (tp[label] + fn[label]) * 100 if (tp[label] + fn[label]) else 0
        f1 = 2 * p * r / (p + r) if (p + r) else 0
        results[label] = {"P": p, "R": r, "F1": f1, "support": tp[label] + fn[label]}
    return results


# ── Comparison ────────────────────────────────────────────────
def compare_models(old_path: Path, new_path: Path, dev_data: list[tuple[str, dict]]):
    """Load both models and print a side-by-side comparison on the dev set."""
    print("\n" + "=" * 72)
    print("MODEL COMPARISON ON DEV SET")
    print("=" * 72)

    old_nlp = spacy.load(old_path)
    new_nlp = spacy.load(new_path)

    old_scores = evaluate(old_nlp, dev_data)
    new_scores = evaluate(new_nlp, dev_data)

    print(f"\n{'Metric':<12} {'Old Model':>12} {'New Model (v2)':>16} {'Delta':>10}")
    print("-" * 52)
    for metric, label in [("Precision", "ents_p"), ("Recall", "ents_r"), ("F1", "ents_f")]:
        old_v = old_scores[label]
        new_v = new_scores[label]
        delta = new_v - old_v
        sign = "+" if delta >= 0 else ""
        print(f"{metric:<12} {old_v:>11.1f}% {new_v:>15.1f}% {sign}{delta:>8.1f}%")

    # Per-label breakdown for the new model
    print(f"\n{'─' * 72}")
    print("PER-LABEL BREAKDOWN (New Model v2)")
    print(f"{'─' * 72}")
    per_label = evaluate_per_label(new_nlp, dev_data)
    print(f"{'Label':<25} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Support':>10}")
    print("-" * 67)
    for label in sorted(per_label):
        s = per_label[label]
        print(f"{label:<25} {s['P']:>9.1f}% {s['R']:>9.1f}% {s['F1']:>9.1f}% {s['support']:>9d}")

    # Labels relevant to section detection
    print(f"\n{'─' * 72}")
    print("SECTION-DETECTION LABELS (used by model_section_parser.py)")
    print(f"{'─' * 72}")
    section_labels = {
        "COMPANIES_WORKED_AT": "experience",
        "YEARS_OF_EXPERIENCE": "experience",
        "DEGREE": "education",
        "COLLEGE_NAME": "education",
        "GRADUATION_YEAR": "education",
    }
    print(f"{'Label':<25} {'Section':<12} {'Old P/R/F1':>18} {'New P/R/F1':>18}")
    print("-" * 75)

    old_per_label = evaluate_per_label(old_nlp, dev_data)
    for label, section in sorted(section_labels.items()):
        old_s = old_per_label.get(label, {"P": 0, "R": 0, "F1": 0})
        new_s = per_label.get(label, {"P": 0, "R": 0, "F1": 0})
        print(f"{label:<25} {section:<12} "
              f"{old_s['P']:>4.0f}/{old_s['R']:>4.0f}/{old_s['F1']:>4.0f}   "
              f"{new_s['P']:>4.0f}/{new_s['R']:>4.0f}/{new_s['F1']:>4.0f}")


# ── Main ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Fine-tune & compare NER models")
    parser.add_argument("--epochs", type=int, default=30,
                        help="Number of training epochs (default: 30)")
    args = parser.parse_args()

    random.seed(42)
    warnings.filterwarnings("ignore", category=UserWarning)

    print("Loading dataset ...")
    dataset = load_dataset(DATA_PATH)

    # 80/20 split
    random.shuffle(dataset)
    split = int(len(dataset) * 0.8)
    train_data = dataset[:split]
    dev_data = dataset[split:]
    print(f"  Train: {len(train_data)}  Dev: {len(dev_data)}")

    # Train the new model
    new_nlp = train_model(train_data, dev_data, NEW_MODEL_PATH, n_iter=args.epochs)

    # Compare
    compare_models(OLD_MODEL_PATH, NEW_MODEL_PATH, dev_data)

    print(f"\n✓ New model saved to: {NEW_MODEL_PATH}")
    print(f"  Old model untouched: {OLD_MODEL_PATH}")


if __name__ == "__main__":
    main()
