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
