import io
import os
import sys
import zipfile
import tempfile
from pathlib import Path

# Ensure sibling modules are importable when run as a package (e.g. gunicorn backend.app:app)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from lxml import etree

from clean_resume import process_docx, _prepend_user_info
from html_to_docx import parse_quill_html

from populate_with_model import populate_from_source_with_model


STATIC_DIR = Path(__file__).resolve().parent / "static"

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="")
CORS(app)


@app.route("/")
def serve_index():
    return app.send_static_file("index.html")


# ═════════════════════════════════════════════════════════════════════
# Template population
# ═════════════════════════════════════════════════════════════════════

def _runs_to_prefix(para_data: dict, ol_counter: int) -> str:
    """Return a bullet/number prefix string based on the paragraph's list type."""
    lt = para_data.get('list_type')
    combined = ''.join(r['text'] for r in para_data.get('runs', [])).strip()
    if lt == 'bullet':
        if not combined.startswith('\u2022'):
            return '\u2022 '
    elif lt == 'ordered':
        return f'{ol_counter}. '
    return ''


def _add_run(parent_p, text, W, bold=False, italic=False, underline=False):
    """Add a <w:r> element with optional formatting to a paragraph."""
    new_r = etree.SubElement(parent_p, f"{{{W}}}r")
    new_rPr = etree.SubElement(new_r, f"{{{W}}}rPr")
    new_rStyle = etree.SubElement(new_rPr, f"{{{W}}}rStyle")
    new_rStyle.set(f"{{{W}}}val", "BodyTextChar")
    new_rFonts = etree.SubElement(new_rPr, f"{{{W}}}rFonts")
    new_rFonts.set(f"{{{W}}}eastAsiaTheme", "minorHAnsi")
    if bold:
        etree.SubElement(new_rPr, f"{{{W}}}b")
    if italic:
        etree.SubElement(new_rPr, f"{{{W}}}i")
    if underline:
        u_el = etree.SubElement(new_rPr, f"{{{W}}}u")
        u_el.set(f"{{{W}}}val", "single")
    new_t = etree.SubElement(new_r, f"{{{W}}}t")
    new_t.text = text
    new_t.set(f"{{{W}}}space", "preserve")


def _replace_user_info_placeholders(
    docx_path: Path,
    user_name: str,
    user_title: str,
    user_department: str,
    user_responsibilities: str = "",
) -> None:
    """
    Fill INSERT_NAME / INSERT_TITLE / INSERT_DEPARTMENT / INSERT_RESPONSIBILITIES
    placeholders inside an already-populated template docx.
    Supports Quill HTML in user_responsibilities to preserve bold/italic/underline
    and bullet/ordered list formatting.
    """
    if not (user_name or user_title or user_department or user_responsibilities):
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
            if "INSERT_RESPONSIBILITIES" in t_node.text:
                if user_responsibilities:
                    parsed = parse_quill_html(user_responsibilities)
                    if parsed:
                        # Build numbered-list counters
                        ol_counter = 0
                        flat_lines = []
                        for p in parsed:
                            if p['list_type'] == 'ordered':
                                ol_counter += 1
                            else:
                                if p['list_type'] != 'ordered':
                                    ol_counter = 0
                            flat_lines.append((p, ol_counter))

                        # First paragraph: replace placeholder text with first line
                        first_para, first_ol = flat_lines[0]
                        first_text = _runs_to_prefix(first_para, first_ol) + ''.join(
                            r['text'] for r in first_para['runs']
                        ).strip()
                        t_node.text = t_node.text.replace(
                            "INSERT_RESPONSIBILITIES", first_text
                        )

                        # Additional paragraphs as rich runs
                        if len(flat_lines) > 1:
                            current_p = t_node.getparent()
                            while current_p is not None and current_p.tag != f"{{{W}}}p":
                                current_p = current_p.getparent()
                            if current_p is not None:
                                from copy import deepcopy
                                orig_pPr = current_p.find(f"{{{W}}}pPr")
                                parent = current_p.getparent()
                                idx = list(parent).index(current_p)
                                for i, (para_data, ol_num) in enumerate(flat_lines[1:], start=1):
                                    new_p = etree.SubElement(parent, f"{{{W}}}p")
                                    parent.remove(new_p)
                                    parent.insert(idx + i, new_p)
                                    if orig_pPr is not None:
                                        new_p.insert(0, deepcopy(orig_pPr))

                                    # Add bullet/number prefix
                                    prefix = _runs_to_prefix(para_data, ol_num)
                                    if prefix:
                                        _add_run(new_p, prefix, W)

                                    # Add each formatted run
                                    for run_data in para_data['runs']:
                                        text = run_data['text']
                                        if not text:
                                            continue
                                        _add_run(
                                            new_p, text, W,
                                            bold=run_data.get('bold', False),
                                            italic=run_data.get('italic', False),
                                            underline=run_data.get('underline', False),
                                        )
                    else:
                        # Fallback: plain text
                        lines = [l for l in user_responsibilities.splitlines() if l.strip()]
                        t_node.text = t_node.text.replace(
                            "INSERT_RESPONSIBILITIES",
                            lines[0] if lines else "",
                        )
                        if len(lines) > 1:
                            current_p = t_node.getparent()
                            while current_p is not None and current_p.tag != f"{{{W}}}p":
                                current_p = current_p.getparent()
                            if current_p is not None:
                                from copy import deepcopy
                                orig_pPr = current_p.find(f"{{{W}}}pPr")
                                parent = current_p.getparent()
                                idx = list(parent).index(current_p)
                                for i, line in enumerate(lines[1:], start=1):
                                    new_p = etree.SubElement(parent, f"{{{W}}}p")
                                    parent.remove(new_p)
                                    parent.insert(idx + i, new_p)
                                    if orig_pPr is not None:
                                        new_p.insert(0, deepcopy(orig_pPr))
                                    _add_run(new_p, line, W)
                else:
                    t_node.text = t_node.text.replace(
                        "INSERT_RESPONSIBILITIES", ""
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
    user_responsibilities = request.form.get("responsibilities", "").strip()

    output = process_docx(file.read())

    if user_name or user_title or user_department:
        output = _prepend_user_info(
            output, user_name, user_title, user_department,
            user_responsibilities,
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
TEMPLATE_PATH = Path(__file__).resolve().parent / "FRM-11110-Template.docx"


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
    user_responsibilities = request.form.get("responsibilities", "").strip()

    tmp_input_path: Path = None
    tmp_output_path: Path = None

    try:
        # ── 1. Save uploaded file to a temp location ──────────
        with tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False
        ) as tmp_in:
            tmp_in.write(file.read())
            tmp_input_path = Path(tmp_in.name)

        # ── 2. Populate using model-driven pipeline ──────────
        with tempfile.NamedTemporaryFile(
            suffix=".docx", delete=False
        ) as tmp_out:
            tmp_output_path = Path(tmp_out.name)

        summary = populate_from_source_with_model(
            source_docx=tmp_input_path,
            template_docx=TEMPLATE_PATH,
            output_docx=tmp_output_path,
        )

        # ── 3. Fill name / title / department placeholders ───
        _replace_user_info_placeholders(
            tmp_output_path,
            user_name,
            user_title,
            user_department,
            user_responsibilities,
        )

        # ── 4. Detect empty sections ─────────────────────────
        empty_sections = []
        if summary["education_paragraphs"] == 0 and summary["education_entries"] == 0:
            empty_sections.append("Education")
        if summary["experience_paragraphs"] == 0:
            empty_sections.append("Experience")

        # ── 5. Send back to caller ───────────────────────────
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
