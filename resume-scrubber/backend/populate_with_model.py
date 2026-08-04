"""
populate_with_model.py
======================

Drop-in orchestration that plugs the trained spaCy model into your existing
DocxPopulator pipeline. It reuses ALL of your existing pieces unchanged:

    TextExtractor.extract_pairs        (your text+xml pairing)
    ModelSectionParser.find_sections   (NEW: model-driven segmentation)
    SectionXmlParser.build_for_section (your XML fragment + numbering builder)
    DocxPopulator.populate_template_files (your injector — already supports
                                           education_xml_paragraphs AND
                                           experience_xml_paragraphs)

The only change vs. your DocxPopulator.populate_from_source is that section
segmentation now comes from ModelSectionParser (trained model + header
heuristics) instead of SectionParser, and BOTH education and experience are
injected as XML (per your "inject the xml of those sections" goal).

Usage
-----
    from populate_with_model import populate_from_source_with_model
    populate_from_source_with_model(
        source_docx = "candidate_cv.docx",
        template_docx = "FRM-11110.docx",
        output_docx = "filled.docx",
        model_path = "./resume_ner_model",
    )
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from lxml import etree

# Your existing modules (imported lazily-friendly at module load).
from parser_get_text import TextExtractor
from parser_get_section_xml import SectionXmlParser
from populate_template import DocxPopulator

# The new model-driven segmenter.
from model_section_parser import ModelSectionParser

W_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ── Combine numbering defs from >1 section (union, dedup by id) ────────────────
def _combine_numbering_defs(
    *defs: Tuple[List[etree._Element], List[etree._Element]],
) -> Tuple[List[etree._Element], List[etree._Element]]:
    """
    Merge several (abstract_defs, num_defs) tuples into one, de-duplicating by
    w:abstractNumId / w:numId. Needed because we now build numbering for BOTH
    the education and experience sections and feed a single combined set to
    DocxPopulator._merge_numbering.
    """
    seen_abs, seen_num = set(), set()
    abstracts: List[etree._Element] = []
    nums: List[etree._Element] = []
    for abstract_defs, num_defs in defs:
        for el in abstract_defs or []:
            aid = el.get(f"{{{W_URI}}}abstractNumId")
            if aid not in seen_abs:
                seen_abs.add(aid)
                abstracts.append(el)
        for el in num_defs or []:
            nid = el.get(f"{{{W_URI}}}numId")
            if nid not in seen_num:
                seen_num.add(nid)
                nums.append(el)
    return abstracts, nums


_BACKEND_DIR = Path(__file__).resolve().parent
_DEFAULT_MODEL_PATH = str(_BACKEND_DIR / "resume_ner_model")


# ── Main entry point ──────────────────────────────────────────────────────────
def populate_from_source_with_model(
    source_docx: Path,
    template_docx: Path,
    output_docx: Path,
    model_path: str = _DEFAULT_MODEL_PATH,
    use_model: bool = True,
    education_as_xml: bool = True,
) -> dict:
    """
    End-to-end population using model-driven section detection.

    education_as_xml=True  -> inject the education section's raw <w:p> XML
                              (mirrors experience; matches "inject the xml").
    education_as_xml=False -> fall back to your EducationParser structured-text
                              path (requires parser_get_education).

    Returns a small summary dict for logging/inspection.
    """
    source_docx = Path(source_docx)
    template_docx = Path(template_docx)
    output_docx = Path(output_docx)

    # ── 1. Unified extraction (unchanged) ────────────────────────────────────
    pairs = TextExtractor.extract_pairs(source_docx)

    # ── 2. Model-driven segmentation (NEW) ───────────────────────────────────
    parser = ModelSectionParser(model_path, use_model=use_model)
    sections = parser.find_sections(pairs)
    education_pairs = sections.get("education", [])
    experience_pairs = sections.get("experience", [])

    # ── 3. Build XML fragments for BOTH sections (your builder, unchanged) ────
    experience_paragraphs, exp_numbering = SectionXmlParser.build_for_section(
        source_docx, experience_pairs
    )

    education_paragraphs: List[etree._Element] = []
    education_entries: List[dict] = []
    edu_numbering = ([], [])

    if education_as_xml:
        education_paragraphs, edu_numbering = SectionXmlParser.build_for_section(
            source_docx, education_pairs
        )
    else:
        # Optional structured-text fallback (your original education path).
        try:
            from parser_get_education import EducationParser  # type: ignore
            edu_text = ModelSectionParser.section_text(education_pairs)
            education_entries = EducationParser.parse(edu_text) if edu_text else []
        except Exception:
            education_entries = []

    # ── 4. Union numbering defs from both sections ───────────────────────────
    combined_numbering = _combine_numbering_defs(edu_numbering, exp_numbering)

    # ── 5. Inject via your existing populator (unchanged) ────────────────────
    DocxPopulator.populate_template_files(
        template_docx=template_docx,
        output_docx=output_docx,
        education_entries=education_entries,
        education_xml_paragraphs=education_paragraphs if education_as_xml else None,
        experience_xml_paragraphs=experience_paragraphs,
        numbering_defs=combined_numbering,
    )

    return {
        "education_paragraphs": len(education_paragraphs),
        "experience_paragraphs": len(experience_paragraphs),
        "education_entries": len(education_entries),
        "numbering_abstract_defs": len(combined_numbering[0]),
        "numbering_num_defs": len(combined_numbering[1]),
        "model_used": parser.nlp is not None,
        "output": str(output_docx),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="populate_with_model.py",
        description="Fill a docx template's Education/Experience sections from a "
                    "source resume, using the trained spaCy model for section "
                    "detection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python populate_with_model.py cv.docx FRM-11110.docx out.docx\n"
            "  python populate_with_model.py cv.docx template.docx out.docx \\\n"
            "      --model ./resume_ner_model\n"
            "  python populate_with_model.py cv.docx template.docx out.docx \\\n"
            "      --education-as-text        # use EducationParser instead of XML\n"
            "  python populate_with_model.py cv.docx template.docx out.docx \\\n"
            "      --no-model                 # header-only segmentation\n"
        ),
    )
    p.add_argument("source_docx", help="Path to the source resume .docx.")
    p.add_argument("template_docx", help="Path to the docx template (e.g. FRM-11110.docx).")
    p.add_argument("output_docx", help="Path to write the populated .docx.")
    p.add_argument("--model", default="./resume_ner_model",
                   help="Path to the fine-tuned spaCy model dir (default ./resume_ner_model).")
    p.add_argument("--no-model", action="store_true",
                   help="Disable the NER model and use header-only segmentation.")
    p.add_argument("--education-as-text", action="store_true",
                   help="Populate education via EducationParser structured text "
                        "instead of injecting its raw XML (default is XML).")
    p.add_argument("--quiet", action="store_true", help="Suppress the summary output.")
    args = p.parse_args(argv)

    # Validate inputs early with clear messages.
    for label, path in (("source", args.source_docx), ("template", args.template_docx)):
        if not Path(path).exists():
            print(f"ERROR: {label} file not found: {path}", file=sys.stderr)
            return 2

    out_parent = Path(args.output_docx).parent
    if out_parent and not out_parent.exists():
        out_parent.mkdir(parents=True, exist_ok=True)

    try:
        summary = populate_from_source_with_model(
            source_docx=args.source_docx,
            template_docx=args.template_docx,
            output_docx=args.output_docx,
            model_path=args.model,
            use_model=not args.no_model,
            education_as_xml=not args.education_as_text,
        )
    except Exception as e:  # surface a clean error, not a raw traceback
        print(f"ERROR: population failed: {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(json.dumps(summary, indent=2))
        if not summary.get("model_used") and not args.no_model:
            print("NOTE: the model was requested but could not be loaded; "
                  "fell back to header-only segmentation. Check --model path.",
                  file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
