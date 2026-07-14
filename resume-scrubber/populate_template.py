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
                    school.get("institution", ""),
                    school.get("degree", ""),
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
    def populate_docx(
        template_docx,
        output_docx,
        education_entries
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
