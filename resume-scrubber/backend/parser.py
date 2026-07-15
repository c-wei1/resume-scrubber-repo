import argparse
import json
import sys

from pathlib import Path
from typing import Any, Dict

from parser_get_text import TextExtractor
from parser_get_education import EducationParser
from parser_get_experience import ExperienceParser
from parser_get_section import SectionParser
from populate_template import DocxPopulator

def main():
    parser = argparse.ArgumentParser(
        description="Extract plain text from a DOCX or TXT file."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to a .docx or .txt file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Optional output file. Defaults to stdout.",
    )

    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)


    # 1. Extract text
    try:
        text = TextExtractor.extract(args.input)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Failed to extract text: {e}", file=sys.stderr)
        sys.exit(3)

    # 2. Write or print the raw text
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote extracted text to {args.output}", file=sys.stderr)
    else:
        print("=" * 70)
        print("TEXTEXTRACTOR OUTPUT")
        print("=" * 70)
        print(text)

    # 3. Run SectionParser
    print()
    print("=" * 70)
    print("SECTIONPARSER OUTPUT")
    print("=" * 70)

    print("SECTION LOOKUP")
    for k, v in SectionParser._get_canonical_lookup().items():
        print(k, "->", v)

    sections = SectionParser.find_sections(text)

    if not sections:
        print("(no sections detected)")
        return

    for name, body in sections.items():
        print()
        print("-" * 70)
        print(f"[{name}]")
        print("-" * 70)
        print(body)

    # 4. Quick summary at the end
    print()
    print("=" * 70)
    print("SECTION SUMMARY")
    print("=" * 70)
    for name, body in sections.items():
        line_count = len(body.splitlines())
        char_count = len(body)
        print(f"  {name:<40} lines={line_count:<4} chars={char_count}")

    # print("\n" + "=" * 70)
    # print("TEXTEXTRACTOR OUTPUT")
    # print("=" * 70)

    # try:
    #     text = TextExtractor.extract(args.input)
    # except ValueError as e:
    #     print(f"Error: {e}", file=sys.stderr)
    #     sys.exit(2)
    # except Exception as e:
    #     print(f"Failed to extract text: {e}", file=sys.stderr)
    #     sys.exit(3)

    # if args.output:
    #     args.output.parent.mkdir(parents=True, exist_ok=True)
    #     args.output.write_text(text, encoding="utf-8")
    #     print(f"Wrote extracted text to {args.output}", file=sys.stderr)
    # else:
    #     print(text)

    print("\nDetected sections:")
    for key in sections:
        print(f"  - {key}")

    print("\n" + "=" * 70)
    print("EDUCATIONPARSER OUTPUT")
    print("=" * 70)

    education_text = sections.get("education")

    if not education_text:
        print("No education section detected.")
    else:
        print("\nEducation section:")
        print("-" * 70)
        print(education_text)

        try:
            entries = EducationParser.parse(education_text)

            print("\nParsed education entries:")
            print(f"Count: {len(entries)}")
            print(json.dumps(entries, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"EducationParser failed: {e}")
    
    education_entries = []
    if sections.get("education"):
        education_entries = EducationParser.parse(sections["education"])

    print("\n" + "=" * 70)
    print("EXPERIENCEPARSER OUTPUT")
    print("=" * 70)

    experience_entries = []
    experience_text = sections.get("experience")

    if not experience_text:
        print("No experience section detected.")
    else:
        print("\nExperience section:")
        print("-" * 70)
        print(experience_text)

        try:
            experience_entries = ExperienceParser.parse(experience_text)

            print("\nParsed experience entries:")
            print(f"Count: {len(experience_entries)}")
            print(json.dumps(experience_entries, indent=2, ensure_ascii=False))

        except Exception as e:
            print(f"ExperienceParser failed: {e}")

    output_path = args.input.with_stem(args.input.stem + "-Populated")

    DocxPopulator.populate_docx(
        "/Users/cwei1/Downloads/FRM-11110-CarolineWei.docx",
        output_path,
        education_entries,
        experience_entries,
    )

    print(f"\nPopulated document saved to: {output_path}")

if __name__ == "__main__":
    main()