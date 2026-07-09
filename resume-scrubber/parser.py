import argparse
import sys
from pathlib import Path

from parser_get_text import TextExtractor
from parser_get_education import EducationParser

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

    print("\n" + "=" * 70)
    print("TEXTEXTRACTOR OUTPUT")
    print("=" * 70)

    try:
        text = TextExtractor.extract(args.input)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Failed to extract text: {e}", file=sys.stderr)
        sys.exit(3)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote extracted text to {args.output}", file=sys.stderr)
    else:
        print(text)

    # print("\n" + "=" * 70)
    # print("EDUCATIONPARSER OUTPUT")
    # print("=" * 70)
    # entries = EducationParser.parse(education_text)
    # print(f"Parsed education entries: {len(entries)}")
    # print(json.dumps(entries, indent=2, ensure_ascii=False))

    # if args.json_out:
    #     report: Dict[str, Any] = {
    #         "input": str(input_path),
    #         "detected_sections": list(sections.keys()),
    #         "education_line_count": len(education_lines),
    #         "education_lines": education_lines,
    #         "line_debug": line_debug,
    #         "parsed_entries": entries,
    #     }
    #     out_path = Path(args.json_out)
    #     out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    #     print(f"\nSaved debug report to: {out_path}")


if __name__ == "__main__":
    main()