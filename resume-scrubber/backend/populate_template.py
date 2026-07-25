"""
DocxPopulator
=============

Insert extracted resume content into the FRM-11110 template.

Design principles:
    * Every SDT and every table cell is guaranteed to end up with at
      least one <w:p>. Empty <w:sdtContent/> and <w:p>-less <w:tc>s
      are the two most common ways to make Word refuse to open a
      document, and this class actively prevents both.
    * Empty inputs never delete template scaffolding. If the caller
      passes `experience_xml_paragraphs=[]`, the placeholder text is
      blanked in place — no paragraphs are removed.
    * Numbering, styles, and content types are merged from the source
      docx so bullet lists and paragraph styles keep rendering.
"""

import zipfile
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import List, Optional, Tuple

from lxml import etree

from parser_get_text import TextExtractor
from parser_get_section import SectionParser
from parser_get_section_xml import SectionXmlParser

try:
    from parser_get_education import EducationParser
except ImportError:
    EducationParser = None

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
W_URI = NS["w"]


class DocxPopulator:

    # ═════════════════════════════════════════════════════════════
    # Public entry points
    # ═════════════════════════════════════════════════════════════

    @staticmethod
    def populate_from_source(
        source_docx: Path,
        template_docx: Path,
        output_docx: Path,
    ) -> None:
        """
        End-to-end population using the unified pipeline:

            TextExtractor  →  (text, xml) pairs
            SectionParser  →  section -> [(text, xml)]
            EducationParser →  structured education entries
            SectionXmlParser → deep-copied XML paragraphs for experience

        Both the structured education entries and the XML experience
        paragraphs come from the SAME segmentation, so they can never
        disagree about which lines belong where.
        """
        source_docx = Path(source_docx)
        template_docx = Path(template_docx)
        output_docx = Path(output_docx)

        # ── 1. Unified extraction ────────────────────────────────
        pairs = TextExtractor.extract_pairs(source_docx)
        sections = SectionParser.find_sections(pairs)

        education_pairs = sections.get("education", [])
        experience_pairs = sections.get("experience", [])

        # ── 2. Text-based education entries ──────────────────────
        education_entries = []
        if EducationParser is not None and education_pairs:
            education_text = SectionParser.section_text(education_pairs)
            education_entries = EducationParser.parse(education_text)

        # ── 3. XML experience paragraphs (deep-copied) ───────────
        experience_paragraphs, numbering_defs = (
            SectionXmlParser.build_for_section(
                source_docx, experience_pairs
            )
        )

        # ── 4. Populate the template ─────────────────────────────
        DocxPopulator.populate_template_files(
            template_docx=template_docx,
            output_docx=output_docx,
            education_entries=education_entries,
            experience_xml_paragraphs=experience_paragraphs,
            numbering_defs=numbering_defs,
        )

    @staticmethod
    def populate_template_files(
        template_docx: Path,
        output_docx: Path,
        education_entries: Optional[List[dict]] = None,
        education_xml_paragraphs: Optional[List[etree._Element]] = None,
        experience_xml_paragraphs: Optional[List[etree._Element]] = None,
        numbering_defs: Optional[
            Tuple[List[etree._Element], List[etree._Element]]
        ] = None,
    ) -> None:
        """
        Low-level entry point. Callers who already have entries + XML
        paragraphs can call this directly.

        Education can be populated via either:
        - education_xml_paragraphs: raw XML paragraphs (preferred)
        - education_entries: structured text entries (fallback)
        """
        template_docx = Path(template_docx)
        output_docx = Path(output_docx)

        education_entries = education_entries or []
        education_xml_paragraphs = education_xml_paragraphs or []
        experience_xml_paragraphs = experience_xml_paragraphs or []

        with tempfile.TemporaryDirectory() as tmp:
            extract_dir = Path(tmp)

            with zipfile.ZipFile(template_docx) as z:
                z.extractall(extract_dir)

            # Merge numbering FIRST so any lists in the inserted
            # experience paragraphs render correctly.
            if numbering_defs is not None:
                DocxPopulator._merge_numbering(extract_dir, numbering_defs)

            document_xml = extract_dir / "word" / "document.xml"
            tree = etree.parse(str(document_xml))
            root = tree.getroot()

            # Education — prefer XML paragraphs, fall back to text entries
            if education_xml_paragraphs:
                DocxPopulator._replace_placeholder_with_xml(
                    root, "INSERT_EDUCATION", education_xml_paragraphs
                )
            else:
                education_lines = DocxPopulator.build_education_section(
                    education_entries
                )
                DocxPopulator._replace_placeholder_text(
                    root, "INSERT_EDUCATION", education_lines
                )
            DocxPopulator._replace_placeholder_text(
                root, "INSERT_CERTIFICATES", []
            )

            # Experience (raw XML)
            DocxPopulator._replace_experience_with_xml(
                root, experience_xml_paragraphs
            )

            # Structural safety net — MUST run after all edits, right
            # before serialization. Prevents empty <w:sdtContent/> and
            # <w:tc>s that don't end with <w:p>.
            DocxPopulator._enforce_ooxml_invariants(root)

            tree.write(
                str(document_xml),
                xml_declaration=True,
                encoding="UTF-8",
                standalone="yes",
            )

            with zipfile.ZipFile(
                output_docx, "w", zipfile.ZIP_DEFLATED
            ) as z:
                for file in extract_dir.rglob("*"):
                    if file.is_file():
                        z.write(file, file.relative_to(extract_dir))

    # ═════════════════════════════════════════════════════════════
    # Education (text-based population)
    # ═════════════════════════════════════════════════════════════

    @staticmethod
    def build_education_section(entries: List[dict]) -> List[str]:
        lines: List[str] = []
        for entry in entries:
            if entry.get("type") == "school":
                school = entry.get("school", {})
                parts = [
                    school.get("institution_header", ""),
                    school.get("year", ""),
                ]
                parts = [p for p in parts if p]
                if parts:
                    lines.append(" | ".join(parts))
            elif entry.get("type") == "certification":
                cert = entry.get("certification", {})
                parts = [
                    cert.get("name", ""),
                    cert.get("year", ""),
                ]
                parts = [p for p in parts if p]
                if parts:
                    lines.append(" | ".join(parts))
        return lines

    @staticmethod
    def _replace_placeholder_text(
        root: etree._Element,
        placeholder: str,
        lines: List[str],
    ) -> None:
        """
        Text-only placeholder replacement.

        EMPTY-SAFE: if `lines` is empty, the placeholder text is blanked
        in place. The surrounding <w:p>, <w:r>, <w:t>, <w:sdtContent>
        scaffolding is preserved — nothing is deleted.
        """
        for t_node in root.xpath(".//w:t", namespaces=NS):
            if not t_node.text or placeholder not in t_node.text:
                continue

            run = t_node.getparent()

            if not lines:
                # Blank the placeholder in place — do NOT remove anything.
                t_node.text = t_node.text.replace(placeholder, "")
                return

            # First line goes into the existing text node
            t_node.text = t_node.text.replace(placeholder, lines[0])

            # Extra lines: alternate <w:br/> runs with cloned text runs
            current_run = run
            for line in lines[1:]:
                # <w:br/> run
                br_run = deepcopy(run)
                for t in br_run.xpath(".//w:t", namespaces=NS):
                    t.getparent().remove(t)
                br = etree.SubElement(br_run, f"{{{W_URI}}}br")

                # Text run
                text_run = deepcopy(run)
                for t in text_run.xpath(".//w:t", namespaces=NS):
                    t.text = line

                current_run.addnext(br_run)
                br_run.addnext(text_run)
                current_run = text_run
            return

    @staticmethod
    def _replace_placeholder_with_xml(
        root: etree._Element,
        placeholder: str,
        xml_paragraphs: List[etree._Element],
    ) -> None:
        """
        Find the paragraph containing `placeholder` and replace it with
        the list of <w:p> elements from xml_paragraphs.

        EMPTY-SAFE: if xml_paragraphs is empty, the placeholder text is
        blanked in place — nothing is removed.
        """
        # Find the paragraph containing the placeholder
        placeholder_para = None
        parent = None
        for t_node in root.xpath(".//w:t", namespaces=NS):
            if t_node.text and placeholder in t_node.text:
                node = t_node
                while node is not None:
                    if node.tag == f"{{{W_URI}}}p":
                        placeholder_para = node
                        parent = node.getparent()
                        break
                    node = node.getparent()
                break

        if placeholder_para is None or parent is None:
            return

        if not xml_paragraphs:
            # Blank the placeholder text in place
            for t_node in placeholder_para.xpath(".//w:t", namespaces=NS):
                if t_node.text and placeholder in t_node.text:
                    t_node.text = t_node.text.replace(placeholder, "")
            return

        # Find insertion index and replace
        insert_index = list(parent).index(placeholder_para)
        parent.remove(placeholder_para)

        for i, para in enumerate(xml_paragraphs):
            parent.insert(insert_index + i, para)

    # ═════════════════════════════════════════════════════════════
    # Experience (raw XML population)
    # ═════════════════════════════════════════════════════════════

    _EXPERIENCE_PLACEHOLDERS = [
        "INSERT_EXPERIENCE1_RESPONSIBILITIES",
        "INSERT_EXPERIENCE1",
        "INSERT_EXPERIENCE2_RESPONSIBILITIES",
        "INSERT_EXPERIENCE2",
    ]

    @staticmethod
    def _replace_experience_with_xml(
        root: etree._Element,
        xml_paragraphs: List[etree._Element],
    ) -> None:
        """
        Replace the two INSERT_EXPERIENCE* placeholder paragraphs (and
        any separator paragraphs between them) with the given XML.

        EMPTY-SAFE: if `xml_paragraphs` is empty, the placeholder text
        is blanked in place. The template scaffolding stays intact.
        This is the critical fix — the previous implementation deleted
        the placeholder paragraphs first and then returned, leaving
        <w:sdtContent/> empty inside a <w:tc>, which Word rejects.
        """
        # ── Empty-safe short-circuit — DO NOT REMOVE ANYTHING ────
        if not xml_paragraphs:
            for t_node in root.xpath(".//w:t", namespaces=NS):
                if not t_node.text:
                    continue
                for ph in DocxPopulator._EXPERIENCE_PLACEHOLDERS:
                    if ph in t_node.text:
                        t_node.text = t_node.text.replace(ph, "")
            return

        # ── Find every paragraph containing a placeholder ────────
        paras_to_remove: List[etree._Element] = []
        first_para: Optional[etree._Element] = None
        parent: Optional[etree._Element] = None

        for t_node in root.xpath(".//w:t", namespaces=NS):
            if not t_node.text:
                continue
            for ph in DocxPopulator._EXPERIENCE_PLACEHOLDERS:
                if ph in t_node.text:
                    node = t_node
                    while node is not None:
                        if node.tag == f"{{{W_URI}}}p":
                            if node not in paras_to_remove:
                                paras_to_remove.append(node)
                                if first_para is None:
                                    first_para = node
                                    parent = node.getparent()
                            break
                        node = node.getparent()
                    break

        if parent is None or first_para is None:
            return

        # Include any separator paragraphs between placeholders
        if len(paras_to_remove) >= 2:
            siblings = list(parent)
            first_idx = siblings.index(paras_to_remove[0])
            last_idx = siblings.index(paras_to_remove[-1])
            for idx in range(first_idx, last_idx + 1):
                if siblings[idx] not in paras_to_remove:
                    paras_to_remove.append(siblings[idx])

        insert_index = list(parent).index(first_para)

        # Remove templates
        for p in paras_to_remove:
            if p.getparent() is not None:
                p.getparent().remove(p)

        # Insert new content
        for i, para in enumerate(xml_paragraphs):
            parent.insert(insert_index + i, para)

    # ═════════════════════════════════════════════════════════════
    # Structural safety net
    # ═════════════════════════════════════════════════════════════

    @staticmethod
    def _enforce_ooxml_invariants(root: etree._Element) -> None:
        """
        Guarantee two invariants that Word requires:

            1. Every <w:sdtContent> contains at least one child.
            2. Every <w:tc> ends with a <w:p>.

        Called immediately before serialization. If any upstream code
        path leaves invalid structure behind (which is easy to do when
        replacing paragraphs), this restores validity in place.
        """
        # 1. Populate empty <w:sdtContent>
        for sc in root.iter(f"{{{W_URI}}}sdtContent"):
            if len(sc) == 0:
                etree.SubElement(sc, f"{{{W_URI}}}p")

        # 2. Ensure every <w:tc> ends with <w:p>
        for tc in root.iter(f"{{{W_URI}}}tc"):
            block_children = [
                c for c in tc
                if c.tag != f"{{{W_URI}}}tcPr"
            ]
            if not block_children:
                etree.SubElement(tc, f"{{{W_URI}}}p")
                continue
            last = block_children[-1]
            if last.tag != f"{{{W_URI}}}p":
                etree.SubElement(tc, f"{{{W_URI}}}p")

    # ═════════════════════════════════════════════════════════════
    # Numbering merge (bullet lists)
    # ═════════════════════════════════════════════════════════════

    @staticmethod
    def _merge_numbering(
        extract_dir: Path,
        numbering_defs: Tuple[List[etree._Element], List[etree._Element]],
    ) -> None:
        abstract_elements, num_elements = numbering_defs
        if not abstract_elements and not num_elements:
            return

        numbering_xml = extract_dir / "word" / "numbering.xml"

        if numbering_xml.exists():
            tree = etree.parse(str(numbering_xml))
            root = tree.getroot()
        else:
            root = etree.Element(
                f"{{{W_URI}}}numbering",
                nsmap={"w": W_URI},
            )
            tree = etree.ElementTree(root)

        existing_abstract_ids = {
            el.get(f"{{{W_URI}}}abstractNumId")
            for el in root.xpath("w:abstractNum", namespaces=NS)
        }
        existing_num_ids = {
            el.get(f"{{{W_URI}}}numId")
            for el in root.xpath("w:num", namespaces=NS)
        }

        for abs_el in abstract_elements:
            aid = abs_el.get(f"{{{W_URI}}}abstractNumId")
            if aid not in existing_abstract_ids:
                root.append(deepcopy(abs_el))

        for num_el in num_elements:
            nid = num_el.get(f"{{{W_URI}}}numId")
            if nid not in existing_num_ids:
                root.append(deepcopy(num_el))

        tree.write(
            str(numbering_xml),
            xml_declaration=True,
            encoding="UTF-8",
            standalone="yes",
        )

        DocxPopulator._register_numbering_part(extract_dir)

    @staticmethod
    def _register_numbering_part(extract_dir: Path) -> None:
        """Ensure numbering.xml is declared in [Content_Types].xml and rels."""
        content_types_path = extract_dir / "[Content_Types].xml"
        if content_types_path.exists():
            ct_tree = etree.parse(str(content_types_path))
            ct_root = ct_tree.getroot()
            CT_NS = ct_root.nsmap.get(
                None,
                "http://schemas.openxmlformats.org/package/2006/content-types",
            )
            numbering_part = "/word/numbering.xml"
            already = any(
                el.get("PartName") == numbering_part
                for el in ct_root.iter(f"{{{CT_NS}}}Override")
            )
            if not already:
                override = etree.SubElement(
                    ct_root, f"{{{CT_NS}}}Override"
                )
                override.set("PartName", numbering_part)
                override.set(
                    "ContentType",
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.numbering+xml",
                )
            ct_tree.write(
                str(content_types_path),
                xml_declaration=True,
                encoding="UTF-8",
                standalone="yes",
            )

        rels_path = extract_dir / "word" / "_rels" / "document.xml.rels"
        if rels_path.exists():
            rels_tree = etree.parse(str(rels_path))
            rels_root = rels_tree.getroot()
            RELS_NS = rels_root.nsmap.get(
                None,
                "http://schemas.openxmlformats.org/package/2006/relationships",
            )
            NUMBERING_REL_TYPE = (
                "http://schemas.openxmlformats.org"
                "/officeDocument/2006/relationships/numbering"
            )
            already = any(
                el.get("Type") == NUMBERING_REL_TYPE for el in rels_root
            )
            if not already:
                existing_ids = {el.get("Id") for el in rels_root}
                n = 1
                while f"rId{n}" in existing_ids:
                    n += 1
                rel = etree.SubElement(
                    rels_root, f"{{{RELS_NS}}}Relationship"
                )
                rel.set("Id", f"rId{n}")
                rel.set("Type", NUMBERING_REL_TYPE)
                rel.set("Target", "numbering.xml")
            rels_tree.write(
                str(rels_path),
                xml_declaration=True,
                encoding="UTF-8",
                standalone="yes",
            )
