import io
import os
import sys
import zipfile
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from lxml import etree

from clean_resume import process_docx, _prepend_user_info

from parser_get_text import TextExtractor
from parser_get_section import SectionParser
from parser_get_section_xml import SectionXmlParser
from populate_template import DocxPopulator

try:
    from parser_get_education import EducationParser
except ImportError:
    EducationParser = None

try:
    from parser_get_experience import ExperienceParser
except ImportError:
    ExperienceParser = None


app = Flask(__name__)
CORS(app)


# ═════════════════════════════════════════════════════════════════════
# Template population
# ═════════════════════════════════════════════════════════════════════

def _replace_user_info_placeholders(
    docx_path: Path,
    user_name: str,
    user_title: str,
    user_department: str,
) -> None:
    """
    Fill INSERT_NAME / INSERT_TITLE / INSERT_DEPARTMENT placeholders inside
    an already-populated template docx.
    """
    if not (user_name or user_title or user_department):
        return

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    with tempfile.TemporaryDirectory() as _td:
        _td = Path(_td)
        with zipfile.ZipFile(str(docx_path), "r") as z:
            z.extractall(_td)

        doc_xml = _td / "word" / "document.xml"
        tree = etree.parse(str(doc_xml))
        root = tree.getroot()

        for t_node in root.iter(f"{{{W}}}t"):
            if t_node.text is None:
                continue
            if "INSERT_NAME" in t_node.text:
                t_node.text = t_node.text.replace(
                    "INSERT_NAME", user_name
                )
            if "INSERT_TITLE" in t_node.text:
                t_node.text = t_node.text.replace(
                    "INSERT_TITLE", user_title
                )
            if "INSERT_DEPARTMENT" in t_node.text:
                t_node.text = t_node.text.replace(
                    "INSERT_DEPARTMENT", user_department
                )

        tree.write(
            str(doc_xml),
            encoding="UTF-8",
            xml_declaration=True,
            standalone=True,
        )

        with zipfile.ZipFile(
            str(docx_path), "w", zipfile.ZIP_DEFLATED
        ) as z:
            for f in _td.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(_td))


# ═════════════════════════════════════════════════════════════════════
# Routes
# ═════════════════════════════════════════════════════════════════════

@app.route("/remove-images", methods=["POST"])
def remove_images():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".docx"):
        return jsonify({"error": "Only .docx files are supported"}), 400

    user_name = request.form.get("name", "").strip()
    user_title = request.form.get("title", "").strip()
    user_department = request.form.get("department", "").strip()

    output = process_docx(file.read())

    if user_name or user_title or user_department:
        output = _prepend_user_info(
            output, user_name, user_title, user_department
        )

    download_name = f"clean_{file.filename}"

    return send_file(
        output,
        mimetype=(
            "application/vnd.openxmlformats-officedocument"
            ".wordprocessingml.document"
        ),
        as_attachment=True,
        download_name=download_name,
        max_age=0,
    )


# Path to the template docx
TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "Downloads"
    / "FRM-11110-CarolineWei.docx"
)
if not TEMPLATE_PATH.exists():
    TEMPLATE_PATH = Path(
        os.path.expanduser("~/Downloads/FRM-11110-CarolineWei.docx")
    )


@app.route("/populate-template", methods=["POST"])
def populate_template():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".docx"):
        return jsonify({"error": "Only .docx files are supported"}), 400

    if not TEMPLATE_PATH.exists():
        return jsonify({"error": "Template file not found on server"}), 500

    user_name = request.form.get("name", "").strip()
    user_title = request.form.get("title", "").strip()
    user_department = request.form.get("department", "").strip()

    tmp_input_path: Path = None
    tmp_output_path: Path = None

    try:
        # ── 1. Save uploaded file to a temp location ──────────
        with tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False
        ) as tmp_in:
            tmp_in.write(file.read())
            tmp_input_path = Path(tmp_in.name)

        # ── 2. Unified pipeline ──────────────────────────────
        # TextExtractor -> SectionParser -> SectionXmlParser
        pairs = TextExtractor.extract_pairs(tmp_input_path)
        sections = SectionParser.find_sections(pairs)

        education_pairs = sections.get("education", [])
        experience_pairs = sections.get("experience", [])

        # Raw education XML (deep-copied) + numbering defs
        education_xml, edu_numbering = (
            SectionXmlParser.build_for_section(
                tmp_input_path, education_pairs
            )
        )

        # Raw experience XML (deep-copied) + numbering defs
        experience_xml, exp_numbering = (
            SectionXmlParser.build_for_section(
                tmp_input_path, experience_pairs
            )
        )

        # Merge numbering defs from both sections
        all_abstract = (edu_numbering[0] if edu_numbering else []) + (exp_numbering[0] if exp_numbering else [])
        all_num = (edu_numbering[1] if edu_numbering else []) + (exp_numbering[1] if exp_numbering else [])
        numbering_defs = (all_abstract, all_num) if (all_abstract or all_num) else None

        # ── 3. Populate the template ─────────────────────────
        with tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False
        ) as tmp_out:
            tmp_output_path = Path(tmp_out.name)

        DocxPopulator.populate_template_files(
            template_docx=TEMPLATE_PATH,
            output_docx=tmp_output_path,
            education_xml_paragraphs=education_xml,
            experience_xml_paragraphs=experience_xml,
            numbering_defs=numbering_defs,
        )

        # ── 4. Fill name / title / department placeholders ───
        _replace_user_info_placeholders(
            tmp_output_path,
            user_name,
            user_title,
            user_department,
        )

        # ── 5. Detect empty sections ─────────────────────────
        empty_sections = []
        if not education_pairs:
            empty_sections.append("Education")
        if not experience_pairs:
            empty_sections.append("Experience")

        # ── 6. Send back to caller ───────────────────────────
        output = io.BytesIO(tmp_output_path.read_bytes())
        output.seek(0)

        download_name = f"populated_{file.filename}"

        response = send_file(
            output,
            mimetype=(
                "application/vnd.openxmlformats-officedocument"
                ".wordprocessingml.document"
            ),
            as_attachment=True,
            download_name=download_name,
            max_age=0,
        )

        if empty_sections:
            response.headers["X-Empty-Sections"] = ",".join(empty_sections)
        response.headers["Access-Control-Expose-Headers"] = "X-Empty-Sections"

        return response

    except Exception as e:
        return jsonify({"error": str(e)}), 500

    finally:
        if tmp_input_path is not None:
            tmp_input_path.unlink(missing_ok=True)
        if tmp_output_path is not None:
            tmp_output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
