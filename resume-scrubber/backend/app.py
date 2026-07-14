import io
import os
import re
import sys
import zipfile
import tempfile
from pathlib import Path

from flask import Flask, request, send_file, jsonify
from flask_cors import CORS
from lxml import etree

from address_identifier import redact_addresses, is_address_line

# Add parent directory to path so we can import the parser modules
# sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from parser_get_text import TextExtractor
from parser_get_education import EducationParser
from parser_get_experience import ExperienceParser
from parser_get_section import SectionParser
from populate_template import DocxPopulator



app = Flask(__name__)
CORS(app)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/package/2006/relationships",
}

IMAGE_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)
HYPERLINK_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
)



# Phone: +1 (555) 123-4567 | 555.123.4567 | (555)123-4567 | international +44 ...
_PHONE_RE = re.compile(
    r'(\+?1[\s.\-]?)?'
    r'(\(?\d{3}\)?[\s.\-]?)'
    r'\d{3}[\s.\-]\d{4}'
)

# Email
_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
)

# URLs (http/https or bare www.)
_URL_RE = re.compile(
    r'(?:https?://|www\.)[^\s<>()\[\]"\']+',
    re.IGNORECASE,
)


def _strip_images(tree):
    """
    Remove image content while preserving any text that may live inside
    drawings/shapes/text boxes.

    Strategy:
      1. For every <w:drawing> and <w:pict>:
         - If it contains any text (<w:t>) or text box (<w:txbx>), keep it.
           Instead, only remove image-specific children (pic:pic, a:blip,
           v:imagedata) from inside it.
         - If it contains no text at all, remove the whole element.
    """
    root = tree.getroot()

    image_containers = (
        root.xpath("//w:drawing", namespaces=NS)
        + root.xpath("//w:pict", namespaces=NS)
    )

    for el in image_containers:

        has_text = bool(el.xpath(".//*[local-name()='t']"))
        has_textbox = bool(el.xpath(".//*[local-name()='txbx']"))

        if has_text or has_textbox:
            # Preserve the container, but strip only image-specific content
            _strip_image_children(el)
        else:
            # No text inside; safe to remove entirely
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)

    return tree


def _strip_image_children(el):
    """
    Remove image-specific children from a drawing/pict element, leaving
    text-carrying content intact.
    """
    # Match any element whose local-name identifies it as an image object
    image_local_names = {
        "pic",        # DrawingML picture
        "blip",       # image reference
        "blipFill",   # image fill
        "imagedata",  # VML image data
        "image",      # generic
    }

    # Walk descendants and remove image-specific nodes
    for node in list(el.iter()):
        localname = etree.QName(node).localname
        if localname in image_local_names:
            parent = node.getparent()
            if parent is not None:
                parent.remove(node)


def _find_pii_spans(text: str) -> list[tuple[int, int]]:
    """Return sorted, merged character spans of all PII matches in text."""
    spans: list[tuple[int, int]] = []
    for pattern in (_EMAIL_RE, _URL_RE, _PHONE_RE):
        for m in pattern.finditer(text):
            spans.append(m.span())
    # Merge overlapping spans
    if not spans:
        return spans
    spans.sort()
    merged = [spans[0]]
    for s, e in spans[1:]:
        if s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def _build_run_map(t_nodes):
    """
    Build a mapping from character offsets in the combined paragraph text
    back to individual <w:t> elements.

    Returns (combined_text, run_map) where run_map is a list of
    (start_offset, end_offset, t_element) tuples.
    """
    run_map: list[tuple[int, int, object]] = []
    offset = 0
    for t_el in t_nodes:
        txt = t_el.text or ''
        run_map.append((offset, offset + len(txt), t_el))
        offset += len(txt)
    combined = ''.join((t.text or '') for t in t_nodes)
    return combined, run_map


REDACTED = ""
def _redact_spans_in_runs(spans, run_map, para):
    """
    Replace PII spans with emtpy text.
    Uses per-node character buffers; the first affected run receives
    the REDACTED marker, remaining chars in that span become empty.
    """
    if not spans:
        return

    # Convert each <w:t>'s text to a mutable list of characters
    buffers = {}
    for idx, (r_start, r_end, t_el) in enumerate(run_map):
        buffers[idx] = list(t_el.text or '')

    for pii_start, pii_end in spans:
        first_run_seen = False

        for idx, (r_start, r_end, t_el) in enumerate(run_map):
            overlap_start = max(pii_start, r_start)
            overlap_end = min(pii_end, r_end)

            if overlap_start >= overlap_end:
                continue

            buf = buffers[idx]
            local_start = overlap_start - r_start
            local_end = overlap_end - r_start

            # Blank the overlapping chars
            for i in range(local_start, local_end):
                buf[i] = ''

            # Insert [REDACTED] marker into the first affected run
            if not first_run_seen:
                buf[local_start] = REDACTED
                first_run_seen = True

    # Write back
    for idx, (r_start, r_end, t_el) in enumerate(run_map):
        t_el.text = ''.join(buffers[idx])


def _scrub_paragraphs(tree):
    """
    Paragraph-level PII detection and redaction.

    For each <w:p>:
      1. Collect all <w:t> nodes and reconstruct the combined logical text
      2. Detect PII (emails, phones, URLs) on the combined text
      3. Map match spans back to individual <w:t> / <w:r> nodes
      4. Blank matched characters; remove runs that become empty
      5. If the whole paragraph is an address line, remove all its runs
    """
    root = tree.getroot()
    for para in root.xpath("//w:p", namespaces=NS):
        t_nodes = para.xpath(".//w:t", namespaces=NS)
        if not t_nodes:
            continue

        combined, run_map = _build_run_map(t_nodes)
        if not combined.strip():
            continue

        # Full-paragraph address check (uses scoring engine)
        if is_address_line(combined):
            for run in list(para.xpath(".//w:r", namespaces=NS)):
                parent = run.getparent()
                if parent is not None:
                    parent.remove(run)
            continue
        

        # Token-level PII: detect on combined text, redact in individual runs
        spans = _find_pii_spans(combined)
        
        _redact_spans_in_runs(spans, run_map, para)

    # Clean up floating "|" separators left after redaction
    _clean_floating_pipes(tree)

    return tree


def _clean_floating_pipes(tree):
    """Remove '|' characters that have no meaningful text on both sides after redaction."""
    root = tree.getroot()
    for para in root.xpath("//w:p", namespaces=NS):
        t_nodes = para.xpath(".//w:t", namespaces=NS)
        if not t_nodes:
            continue

        # Work on the combined paragraph text to detect floating pipes
        combined = ''.join((t.text or '') for t in t_nodes)

        if '|' not in combined:
            continue

        # Remove pipes that have only whitespace (or nothing) on either side:
        # " | " at end, "text | |", "| text |", leading "|", trailing "|"
        # Strategy: split on |, keep only non-empty segments, rejoin
        parts = [p.strip() for p in combined.split('|')]
        cleaned = ' | '.join(p for p in parts if p)

        if cleaned == combined:
            continue

        # Redistribute the cleaned text back into the <w:t> nodes
        # Put all text in the first node, clear the rest
        if t_nodes:
            t_nodes[0].text = cleaned
            for t_el in t_nodes[1:]:
                t_el.text = ''

def _scrub_metadata_xml(xml_file: Path):
    tree = etree.parse(str(xml_file))
    root = tree.getroot()

    for tag in root.xpath(".//*"):
        if not tag.text:
            continue

        localname = etree.QName(tag).localname

        if localname in {
            "creator",
            "lastModifiedBy",
            "description",
            "subject",
            "title",
            "keywords",
            "category",
        }:
            text = tag.text
            text = _EMAIL_RE.sub("", text)
            text = _PHONE_RE.sub("", text)
            text = _URL_RE.sub("", text)
            tag.text = text.strip()

    tree.write(
        str(xml_file),
        encoding="UTF-8",
        xml_declaration=True
    )


def _unwrap_hyperlinks(tree):
    """
    Remove <w:hyperlink> wrappers and replace their visible text with
    [REDACTED]. This ensures the hyperlink target is stripped, but the
    reader sees that something was redacted where the link used to be.
    """
    root = tree.getroot()

    for hl in root.xpath("//w:hyperlink", namespaces=NS):
        parent = hl.getparent()
        if parent is None:
            continue

        # Blank all <w:t> nodes inside the hyperlink, put [REDACTED] in the first
        t_nodes = hl.xpath(".//w:t", namespaces=NS)
        for i, t_el in enumerate(t_nodes):
            t_el.text = REDACTED if i == 0 else ""

        # Move hyperlink's children up to its parent, preserving formatting
        insert_idx = parent.index(hl)
        for child in list(hl):
            hl.remove(child)
            parent.insert(insert_idx, child)
            insert_idx += 1

        parent.remove(hl)

    return tree

def _process_tree(tree):
    _unwrap_hyperlinks(tree)
    _scrub_paragraphs(tree)
    _strip_images(tree)
    return tree


def _strip_rels(rels_file: Path):
    """Remove image and hyperlink relationships from a .rels file."""
    if not rels_file.exists():
        return
    rels_tree = etree.parse(str(rels_file))
    rels_root = rels_tree.getroot()
    remove_types = {IMAGE_REL_TYPE, HYPERLINK_REL_TYPE}
    for rel in list(rels_root):
        if rel.get("Type") in remove_types:
            rels_root.remove(rel)
    rels_tree.write(str(rels_file), encoding="UTF-8", xml_declaration=True)


def process_docx(input_bytes: bytes) -> io.BytesIO:
    with tempfile.TemporaryDirectory() as _tmpdir:
        tmpdir = Path(_tmpdir)

        with zipfile.ZipFile(io.BytesIO(input_bytes), "r") as z:
            z.extractall(tmpdir)

        word_dir = tmpdir / "word"

        # Scrub metadata
        docprops_dir = tmpdir / "docProps"

        for xml_file in docprops_dir.glob("*.xml"):
            print("Scrubbing metadata:", xml_file)
            _scrub_metadata_xml(xml_file)

        # Main document
        doc_xml = word_dir / "document.xml"
        if doc_xml.exists():
            tree = etree.parse(str(doc_xml))
            _process_tree(tree)
            tree.write(str(doc_xml), encoding="UTF-8", xml_declaration=True)

        # Headers & footers
        for xml_file in (
            list(word_dir.glob("header*.xml")) + list(word_dir.glob("footer*.xml"))
        ):
            tree = etree.parse(str(xml_file))
            _process_tree(tree)
            tree.write(str(xml_file), encoding="UTF-8", xml_declaration=True)

        # Relationships (images + hyperlinks)
        _strip_rels(word_dir / "_rels" / "document.xml.rels")
        for header_rels in (word_dir / "_rels").glob("header*.xml.rels"):
            _strip_rels(header_rels)
        for footer_rels in (word_dir / "_rels").glob("footer*.xml.rels"):
            _strip_rels(footer_rels)

        # Media files
        media_dir = word_dir / "media"
        if media_dir.exists():
            for f in media_dir.iterdir():
                if f.is_file():
                    f.unlink()

        # Repack
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as z:
            for f in tmpdir.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(tmpdir))
        output.seek(0)

        return output


@app.route("/remove-images", methods=["POST"])
def remove_images():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".docx"):
        return jsonify({"error": "Only .docx files are supported"}), 400

    output = process_docx(file.read())
    download_name = f"scrubbed_{file.filename}"

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=download_name,
        max_age=0,
    )


# Path to the template docx
TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "Downloads" / "FRM-11110-CarolineWei.docx"
# Fallback: check common location
if not TEMPLATE_PATH.exists():
    TEMPLATE_PATH = Path(os.path.expanduser("~/Downloads/FRM-11110-CarolineWei.docx"))


@app.route("/populate-template", methods=["POST"])
def populate_template():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]

    if not file.filename.lower().endswith(".docx"):
        return jsonify({"error": "Only .docx files are supported"}), 400

    if not TEMPLATE_PATH.exists():
        return jsonify({"error": "Template file not found on server"}), 500

    try:
        # Save uploaded file to a temp location
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_in:
            tmp_in.write(file.read())
            tmp_input_path = Path(tmp_in.name)

        # Extract text from the uploaded resume
        text = TextExtractor.extract(tmp_input_path)

        # Find sections
        sections = SectionParser.find_sections(text)

        # Parse education
        education_entries = []
        education_text = sections.get("education")
        if education_text:
            education_entries = EducationParser.parse(education_text)

        # Parse experience
        experience_entries = []
        experience_text = sections.get("experience")
        if experience_text:
            experience_entries = ExperienceParser.parse(experience_text)

        # Populate the template
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_out:
            tmp_output_path = Path(tmp_out.name)

        DocxPopulator.populate_docx(
            str(TEMPLATE_PATH),
            str(tmp_output_path),
            education_entries,
            experience_entries,
        )

        # Read the populated file into memory
        output = io.BytesIO(tmp_output_path.read_bytes())
        output.seek(0)

        # Clean up temp files
        tmp_input_path.unlink(missing_ok=True)
        tmp_output_path.unlink(missing_ok=True)

        download_name = f"populated_{file.filename}"

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            as_attachment=True,
            download_name=download_name,
            max_age=0,
        )

    except Exception as e:
        # Clean up on error
        if 'tmp_input_path' in locals():
            tmp_input_path.unlink(missing_ok=True)
        if 'tmp_output_path' in locals():
            tmp_output_path.unlink(missing_ok=True)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
    core_xml = tmpdir / "docProps" / "core.xml"

    if core_xml.exists():
        print(core_xml.read_text(errors="ignore"))
