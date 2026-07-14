import zipfile
import tempfile
from copy import deepcopy
from pathlib import Path
from lxml import etree

from parser_get_education import EducationParser

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
}

class DocxPopulator:

    @staticmethod
    def replace_placeholder(root, placeholder, lines):

        for node in root.xpath(".//w:t", namespaces=NS):

            if not node.text or placeholder not in node.text:
                continue

            run = node.getparent()

            # No content -> remove placeholder
            if not lines:
                node.text = node.text.replace(placeholder, "")
                return

            # Replace placeholder with first line
            node.text = node.text.replace(
                placeholder,
                lines[0]
            )

            current_run = run

            # Add remaining lines with Word line breaks
            for line in lines[1:]:

                br_run = deepcopy(run)

                # remove copied text nodes
                for t in br_run.xpath(".//w:t", namespaces=NS):
                    t.getparent().remove(t)

                br = etree.Element(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
                )

                br_run.append(br)

                text_run = deepcopy(run)

                for t in text_run.xpath(".//w:t", namespaces=NS):
                    t.text = line

                current_run.addnext(br_run)
                br_run.addnext(text_run)

                current_run = text_run

            return

    @staticmethod
    def build_education_section(entries):

        lines = []

        for entry in entries:

            if entry["type"] == "school":

                school = entry["school"]

                parts = [
                    school.get("institution_header", ""),
                    school.get("year", ""),
                ]

                parts = [p for p in parts if p]

                if parts:
                    lines.append(" | ".join(parts))

            elif entry["type"] == "certification":

                cert = entry["certification"]

                parts = [
                    cert.get("name", ""),
                    cert.get("year", ""),
                ]

                parts = [p for p in parts if p]

                if parts:
                    lines.append(" | ".join(parts))

        return lines

    @staticmethod
    def populate_experience_section(root, experience_entries):
        """
        Populate the experience section by cloning the first experience
        template block (header paragraph + responsibilities paragraph +
        separator paragraph) for each entry from ExperienceParser.

        Template has INSERT_EXPERIENCE1 / INSERT_EXPERIENCE1_RESPONSIBILITIES
        and INSERT_EXPERIENCE2 / INSERT_EXPERIENCE2_RESPONSIBILITIES as
        examples.  We use the first block as the template, clone it for
        each real entry, and remove the originals.
        """
        W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

        # ── Locate the template paragraphs ───────────────────────────
        # Find all <w:t> nodes that contain our experience placeholders
        header_node_1 = None
        resp_node_1 = None
        header_node_2 = None
        resp_node_2 = None

        for t_node in root.xpath(".//w:t", namespaces=NS):
            if t_node.text and "INSERT_EXPERIENCE1_RESPONSIBILITIES" in t_node.text:
                resp_node_1 = t_node
            elif t_node.text and "INSERT_EXPERIENCE1" in t_node.text:
                header_node_1 = t_node
            elif t_node.text and "INSERT_EXPERIENCE2_RESPONSIBILITIES" in t_node.text:
                resp_node_2 = t_node
            elif t_node.text and "INSERT_EXPERIENCE2" in t_node.text:
                header_node_2 = t_node

        if header_node_1 is None or resp_node_1 is None:
            return

        # Walk up to the <w:p> paragraph elements
        def get_paragraph(t_node):
            n = t_node
            while n is not None:
                if n.tag == f"{{{W}}}p":
                    return n
                n = n.getparent()
            return None

        header_para_1 = get_paragraph(header_node_1)
        resp_para_1 = get_paragraph(resp_node_1)
        header_para_2 = get_paragraph(header_node_2) if header_node_2 is not None else None
        resp_para_2 = get_paragraph(resp_node_2) if resp_node_2 is not None else None

        if header_para_1 is None or resp_para_1 is None:
            return

        parent = header_para_1.getparent()

        # Find the separator paragraph (empty paragraph between exp1 and exp2)
        separator_para = None
        sibling = resp_para_1.getnext()
        if sibling is not None and header_para_2 is not None:
            # The paragraph between resp1 and header2 is the separator
            if sibling is not header_para_2:
                separator_para = sibling

        # ── Build new paragraphs for each experience entry ───────────
        new_paragraphs = []

        for i, entry in enumerate(experience_entries):
            job_header_text = "\n".join(entry.get("job_header", []))
            description_lines = entry.get("description", [])
            description_text = "\n".join(description_lines)

            # Clone header paragraph and bold the text
            W_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            h_para = deepcopy(header_para_1)
            for run in h_para.xpath(".//w:r", namespaces=NS):
                for t_node in run.xpath("w:t", namespaces=NS):
                    if t_node.text and "INSERT_EXPERIENCE1" in t_node.text:
                        t_node.text = t_node.text.replace(
                            "INSERT_EXPERIENCE1", job_header_text
                        )
                # Add or update <w:b/> in the run's <w:rPr>
                rpr = run.find(f"{{{W_URI}}}rPr")
                if rpr is None:
                    rpr = etree.SubElement(run, f"{{{W_URI}}}rPr")
                    run.insert(0, rpr)
                if rpr.find(f"{{{W_URI}}}b") is None:
                    etree.SubElement(rpr, f"{{{W_URI}}}b")
            new_paragraphs.append(h_para)

            # Clone responsibilities paragraph — one indented line per
            # description item, each separated by a Word line break.
            r_para = deepcopy(resp_para_1)

            # Find the tab run and text run in the template
            tab_run_template = None
            text_run_template = None
            for run in r_para.xpath(".//w:r", namespaces=NS):
                if run.xpath("w:tab", namespaces=NS):
                    tab_run_template = run
                for t_node in run.xpath("w:t", namespaces=NS):
                    if t_node.text and "INSERT_EXPERIENCE1_RESPONSIBILITIES" in t_node.text:
                        text_run_template = run

            if text_run_template is not None and description_lines:
                # Get the run's parent (the paragraph)
                run_parent = text_run_template.getparent()

                # Remove the placeholder text run
                run_parent.remove(text_run_template)
                # Remove the tab run too (we'll re-add per line)
                if tab_run_template is not None and tab_run_template.getparent() is not None:
                    run_parent.remove(tab_run_template)

                for idx, desc_line in enumerate(description_lines):
                    # Add line break before each line (except the first)
                    if idx > 0:
                        br_run = deepcopy(tab_run_template) if tab_run_template is not None else etree.SubElement(run_parent, f"{{{W_URI}}}r")
                        # Clear children and add a <w:br/>
                        for child in list(br_run):
                            br_run.remove(child)
                        # Copy rPr from template if available
                        if tab_run_template is not None:
                            for rpr in tab_run_template.xpath("w:rPr", namespaces=NS):
                                br_run.append(deepcopy(rpr))
                        br_el = etree.SubElement(br_run, f"{{{W_URI}}}br")
                        run_parent.append(br_run)

                    # Tab run
                    if tab_run_template is not None:
                        run_parent.append(deepcopy(tab_run_template))

                    # Text run
                    t_run = deepcopy(text_run_template)
                    for t_node in t_run.xpath("w:t", namespaces=NS):
                        t_node.text = desc_line
                        t_node.set(f"{{{W_URI}}}space", "preserve")
                    run_parent.append(t_run)

            elif text_run_template is not None:
                # No description — clear the placeholder
                for t_node in text_run_template.xpath("w:t", namespaces=NS):
                    if t_node.text and "INSERT_EXPERIENCE1_RESPONSIBILITIES" in t_node.text:
                        t_node.text = t_node.text.replace(
                            "INSERT_EXPERIENCE1_RESPONSIBILITIES", ""
                        )

            new_paragraphs.append(r_para)

            # Add separator between entries (not after the last one)
            if separator_para is not None and i < len(experience_entries) - 1:
                new_paragraphs.append(deepcopy(separator_para))

        # ── Remove original template paragraphs ─────────────────────
        to_remove = [header_para_1, resp_para_1]
        if separator_para is not None:
            to_remove.append(separator_para)
        if header_para_2 is not None:
            to_remove.append(header_para_2)
        if resp_para_2 is not None:
            to_remove.append(resp_para_2)

        # Find insertion point (before the first template paragraph)
        insert_index = list(parent).index(header_para_1)

        for p in to_remove:
            if p.getparent() is not None:
                p.getparent().remove(p)

        # Insert new paragraphs at the original position
        for j, para in enumerate(new_paragraphs):
            parent.insert(insert_index + j, para)

    @staticmethod
    def populate_docx(
        template_docx,
        output_docx,
        education_entries,
        experience_entries=None,
    ):

        template_docx = Path(template_docx)
        output_docx = Path(output_docx)

        with tempfile.TemporaryDirectory() as tmp:

            extract_dir = Path(tmp)

            with zipfile.ZipFile(template_docx) as z:
                z.extractall(extract_dir)

            document_xml = (
                extract_dir
                / "word"
                / "document.xml"
            )

            tree = etree.parse(str(document_xml))
            root = tree.getroot()

            education_lines = DocxPopulator.build_education_section(
                education_entries
            )

            DocxPopulator.replace_placeholder(
                root,
                "INSERT_EDUCATION",
                education_lines,
            )

            DocxPopulator.replace_placeholder(
                root,
                "INSERT_CERTIFICATES",
                [],
            )

            if experience_entries:
                DocxPopulator.populate_experience_section(
                    root,
                    experience_entries,
                )

            tree.write(
                str(document_xml),
                xml_declaration=True,
                encoding="UTF-8",
                standalone="yes",
            )

            with zipfile.ZipFile(
                output_docx,
                "w",
                zipfile.ZIP_DEFLATED,
            ) as z:

                for file in extract_dir.rglob("*"):
                    if file.is_file():
                        z.write(
                            file,
                            file.relative_to(extract_dir)
                        )
