"""
Batch script: scrub and parse all .docx resumes from a folder.
- Scrubbed versions → test_resumes/scrubbed/
- Parsed (populated template) versions → test_resumes/parsed/
"""

import sys
from pathlib import Path

# Ensure backend modules are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import process_docx, TEMPLATE_PATH
from parser_get_text import TextExtractor
from parser_get_section import SectionParser
from parser_get_education import EducationParser
from parser_get_experience import ExperienceParser
from populate_template import DocxPopulator

INPUT_DIR = Path("/Users/cwei1/Library/CloudStorage/OneDrive-GileadSciences/Desktop/cv_checker_script/test_resumes")
PARSED_DIR = INPUT_DIR / "parsed"
SCRUBBED_DIR = INPUT_DIR / "scrubbed"


def main():
    PARSED_DIR.mkdir(exist_ok=True)
    SCRUBBED_DIR.mkdir(exist_ok=True)

    docx_files = sorted(INPUT_DIR.glob("*.docx"))
    if not docx_files:
        print(f"No .docx files found in {INPUT_DIR}")
        return

    print(f"Found {len(docx_files)} resume(s) to process.\n")

    for docx_path in docx_files:
        print(f"{'=' * 60}")
        print(f"Processing: {docx_path.name}")
        print(f"{'=' * 60}")

        # ── Scrub ────────────────────────────────────────────────
        try:
            scrubbed_output = process_docx(docx_path.read_bytes())
            scrubbed_path = SCRUBBED_DIR / f"scrubbed_{docx_path.name}"
            scrubbed_path.write_bytes(scrubbed_output.read())
            print(f"  ✓ Scrubbed → {scrubbed_path.name}")
        except Exception as e:
            print(f"  ✗ Scrub failed: {e}")

        # ── Parse & Populate Template ────────────────────────────
        try:
            text = TextExtractor.extract(docx_path)
            sections = SectionParser.find_sections(text)

            education_entries = []
            if sections.get("education"):
                education_entries = EducationParser.parse(sections["education"])

            experience_entries = []
            if sections.get("experience"):
                experience_entries = ExperienceParser.parse(sections["experience"])

            parsed_path = PARSED_DIR / f"parsed_{docx_path.name}"

            if not TEMPLATE_PATH.exists():
                print(f"  ✗ Template not found at {TEMPLATE_PATH}")
            else:
                DocxPopulator.populate_docx(
                    str(TEMPLATE_PATH),
                    str(parsed_path),
                    education_entries,
                    experience_entries,
                )
                print(f"  ✓ Parsed  → {parsed_path.name}")
                print(f"    Education: {len(education_entries)} entries, Experience: {len(experience_entries)} entries")

        except Exception as e:
            print(f"  ✗ Parse failed: {e}")

        print()

    print("Done.")


if __name__ == "__main__":
    main()
