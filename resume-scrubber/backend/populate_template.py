# import zipfile
# import tempfile
# from copy import deepcopy
# from pathlib import Path
# from lxml import etree

# NS = {
#     "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# }

# class DocxPopulator:

#     @staticmethod
#     def replace_placeholder(root, placeholder, lines):

#         for node in root.xpath(".//w:t", namespaces=NS):

#             if not node.text or placeholder not in node.text:
#                 continue

#             run = node.getparent()

#             # No content -> remove placeholder
#             if not lines:
#                 node.text = node.text.replace(placeholder, "")
#                 return

#             # Replace placeholder with first line
#             node.text = node.text.replace(
#                 placeholder,
#                 lines[0]
#             )

#             current_run = run

#             # Add remaining lines with Word line breaks
#             for line in lines[1:]:

#                 br_run = deepcopy(run)

#                 # remove copied text nodes
#                 for t in br_run.xpath(".//w:t", namespaces=NS):
#                     t.getparent().remove(t)

#                 br = etree.Element(
#                     "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br"
#                 )

#                 br_run.append(br)

#                 text_run = deepcopy(run)

#                 for t in text_run.xpath(".//w:t", namespaces=NS):
#                     t.text = line

#                 current_run.addnext(br_run)
#                 br_run.addnext(text_run)

#                 current_run = text_run

#             return

#     @staticmethod
#     def build_education_section(entries):

#         lines = []

#         for entry in entries:

#             if entry["type"] == "school":

#                 school = entry["school"]

#                 parts = [
#                     school.get("institution_header", ""),
#                     school.get("year", ""),
#                 ]

#                 parts = [p for p in parts if p]

#                 if parts:
#                     lines.append(" | ".join(parts))

#             elif entry["type"] == "certification":

#                 cert = entry["certification"]

#                 parts = [
#                     cert.get("name", ""),
#                     cert.get("year", ""),
#                 ]

#                 parts = [p for p in parts if p]

#                 if parts:
#                     lines.append(" | ".join(parts))

#         return lines

#     @staticmethod
#     def populate_experience_section(root, experience_entries):
#         """
#         Populate the experience section by cloning the first experience
#         template block (header paragraph + responsibilities paragraph +
#         separator paragraph) for each entry from ExperienceParser.

#         Template has INSERT_EXPERIENCE1 / INSERT_EXPERIENCE1_RESPONSIBILITIES
#         and INSERT_EXPERIENCE2 / INSERT_EXPERIENCE2_RESPONSIBILITIES as
#         examples.  We use the first block as the template, clone it for
#         each real entry, and remove the originals.
#         """
#         W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

#         # ── Locate the template paragraphs ───────────────────────────
#         # Find all <w:t> nodes that contain our experience placeholders
#         header_node_1 = None
#         resp_node_1 = None
#         header_node_2 = None
#         resp_node_2 = None

#         for t_node in root.xpath(".//w:t", namespaces=NS):
#             if t_node.text and "INSERT_EXPERIENCE1_RESPONSIBILITIES" in t_node.text:
#                 resp_node_1 = t_node
#             elif t_node.text and "INSERT_EXPERIENCE1" in t_node.text:
#                 header_node_1 = t_node
#             elif t_node.text and "INSERT_EXPERIENCE2_RESPONSIBILITIES" in t_node.text:
#                 resp_node_2 = t_node
#             elif t_node.text and "INSERT_EXPERIENCE2" in t_node.text:
#                 header_node_2 = t_node

#         if header_node_1 is None or resp_node_1 is None:
#             return

#         # Walk up to the <w:p> paragraph elements
#         def get_paragraph(t_node):
#             n = t_node
#             while n is not None:
#                 if n.tag == f"{{{W}}}p":
#                     return n
#                 n = n.getparent()
#             return None

#         header_para_1 = get_paragraph(header_node_1)
#         resp_para_1 = get_paragraph(resp_node_1)
#         header_para_2 = get_paragraph(header_node_2) if header_node_2 is not None else None
#         resp_para_2 = get_paragraph(resp_node_2) if resp_node_2 is not None else None

#         if header_para_1 is None or resp_para_1 is None:
#             return

#         parent = header_para_1.getparent()

#         # Find the separator paragraph (empty paragraph between exp1 and exp2)
#         separator_para = None
#         sibling = resp_para_1.getnext()
#         if sibling is not None and header_para_2 is not None:
#             # The paragraph between resp1 and header2 is the separator
#             if sibling is not header_para_2:
#                 separator_para = sibling

#         # ── Build new paragraphs for each experience entry ───────────
#         new_paragraphs = []

#         for i, entry in enumerate(experience_entries):
#             job_header_text = "\n".join(entry.get("job_header", []))
#             description_lines = entry.get("description", [])
#             description_text = "\n".join(description_lines)

#             # Clone header paragraph and bold the text
#             W_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
#             h_para = deepcopy(header_para_1)
#             for run in h_para.xpath(".//w:r", namespaces=NS):
#                 for t_node in run.xpath("w:t", namespaces=NS):
#                     if t_node.text and "INSERT_EXPERIENCE1" in t_node.text:
#                         t_node.text = t_node.text.replace(
#                             "INSERT_EXPERIENCE1", job_header_text
#                         )
#                 # Add or update <w:b/> in the run's <w:rPr>
#                 rpr = run.find(f"{{{W_URI}}}rPr")
#                 if rpr is None:
#                     rpr = etree.SubElement(run, f"{{{W_URI}}}rPr")
#                     run.insert(0, rpr)
#                 if rpr.find(f"{{{W_URI}}}b") is None:
#                     etree.SubElement(rpr, f"{{{W_URI}}}b")
#             new_paragraphs.append(h_para)

#             # Clone responsibilities paragraph — one indented line per
#             # description item, each separated by a Word line break.
#             r_para = deepcopy(resp_para_1)

#             # Find the tab run and text run in the template
#             tab_run_template = None
#             text_run_template = None
#             for run in r_para.xpath(".//w:r", namespaces=NS):
#                 if run.xpath("w:tab", namespaces=NS):
#                     tab_run_template = run
#                 for t_node in run.xpath("w:t", namespaces=NS):
#                     if t_node.text and "INSERT_EXPERIENCE1_RESPONSIBILITIES" in t_node.text:
#                         text_run_template = run

#             if text_run_template is not None and description_lines:
#                 # Get the run's parent (the paragraph)
#                 run_parent = text_run_template.getparent()

#                 # Remove the placeholder text run
#                 run_parent.remove(text_run_template)
#                 # Remove the tab run too (we'll re-add per line)
#                 if tab_run_template is not None and tab_run_template.getparent() is not None:
#                     run_parent.remove(tab_run_template)

#                 for idx, desc_line in enumerate(description_lines):
#                     # Add line break before each line (except the first)
#                     if idx > 0:
#                         br_run = deepcopy(tab_run_template) if tab_run_template is not None else etree.SubElement(run_parent, f"{{{W_URI}}}r")
#                         # Clear children and add a <w:br/>
#                         for child in list(br_run):
#                             br_run.remove(child)
#                         # Copy rPr from template if available
#                         if tab_run_template is not None:
#                             for rpr in tab_run_template.xpath("w:rPr", namespaces=NS):
#                                 br_run.append(deepcopy(rpr))
#                         br_el = etree.SubElement(br_run, f"{{{W_URI}}}br")
#                         run_parent.append(br_run)

#                     # Tab run
#                     if tab_run_template is not None:
#                         run_parent.append(deepcopy(tab_run_template))

#                     # Text run
#                     t_run = deepcopy(text_run_template)
#                     for t_node in t_run.xpath("w:t", namespaces=NS):
#                         t_node.text = desc_line
#                         t_node.set(f"{{{W_URI}}}space", "preserve")
#                     run_parent.append(t_run)

#             elif text_run_template is not None:
#                 # No description — clear the placeholder
#                 for t_node in text_run_template.xpath("w:t", namespaces=NS):
#                     if t_node.text and "INSERT_EXPERIENCE1_RESPONSIBILITIES" in t_node.text:
#                         t_node.text = t_node.text.replace(
#                             "INSERT_EXPERIENCE1_RESPONSIBILITIES", ""
#                         )

#             new_paragraphs.append(r_para)

#             # Add separator between entries (not after the last one)
#             if separator_para is not None and i < len(experience_entries) - 1:
#                 new_paragraphs.append(deepcopy(separator_para))

#         # ── Remove original template paragraphs ─────────────────────
#         to_remove = [header_para_1, resp_para_1]
#         if separator_para is not None:
#             to_remove.append(separator_para)
#         if header_para_2 is not None:
#             to_remove.append(header_para_2)
#         if resp_para_2 is not None:
#             to_remove.append(resp_para_2)

#         # Find insertion point (before the first template paragraph)
#         insert_index = list(parent).index(header_para_1)

#         for p in to_remove:
#             if p.getparent() is not None:
#                 p.getparent().remove(p)

#         # Insert new paragraphs at the original position
#         for j, para in enumerate(new_paragraphs):
#             parent.insert(insert_index + j, para)

#     @staticmethod
#     def populate_docx(
#         template_docx,
#         output_docx,
#         education_entries,
#         experience_entries=None,
#     ):

#         template_docx = Path(template_docx)
#         output_docx = Path(output_docx)

#         with tempfile.TemporaryDirectory() as tmp:

#             extract_dir = Path(tmp)

#             with zipfile.ZipFile(template_docx) as z:
#                 z.extractall(extract_dir)

#             document_xml = (
#                 extract_dir
#                 / "word"
#                 / "document.xml"
#             )

#             tree = etree.parse(str(document_xml))
#             root = tree.getroot()

#             education_lines = DocxPopulator.build_education_section(
#                 education_entries
#             )

#             DocxPopulator.replace_placeholder(
#                 root,
#                 "INSERT_EDUCATION",
#                 education_lines,
#             )

#             DocxPopulator.replace_placeholder(
#                 root,
#                 "INSERT_CERTIFICATES",
#                 [],
#             )

#             if experience_entries:
#                 DocxPopulator.populate_experience_section(
#                     root,
#                     experience_entries,
#                 )

#             tree.write(
#                 str(document_xml),
#                 xml_declaration=True,
#                 encoding="UTF-8",
#                 standalone="yes",
#             )

#             with zipfile.ZipFile(
#                 output_docx,
#                 "w",
#                 zipfile.ZIP_DEFLATED,
#             ) as z:

#                 for file in extract_dir.rglob("*"):
#                     if file.is_file():
#                         z.write(
#                             file,
#                             file.relative_to(extract_dir)
#                         )

#     @staticmethod
#     def _find_placeholder_range(root, placeholder):
#         """
#         Find the paragraph containing the given placeholder text.
#         Returns (parent, paragraph_element) or (None, None).
#         """
#         for t_node in root.xpath(".//w:t", namespaces=NS):
#             if t_node.text and placeholder in t_node.text:
#                 # Walk up to the <w:p>
#                 node = t_node
#                 while node is not None:
#                     if node.tag == f"{{{NS['w']}}}p":
#                         return node.getparent(), node
#                     node = node.getparent()
#         return None, None

#     @staticmethod
#     def _replace_placeholder_with_xml(root, placeholder, xml_paragraphs):
#         """
#         Find the paragraph containing `placeholder` and replace it with
#         the list of <w:p> elements from xml_paragraphs.
#         If xml_paragraphs is empty, just remove the placeholder text.
#         """
#         parent, placeholder_para = DocxPopulator._find_placeholder_range(
#             root, placeholder
#         )
#         if parent is None or placeholder_para is None:
#             return

#         if not xml_paragraphs:
#             # Just blank the placeholder text
#             for t_node in placeholder_para.xpath(".//w:t", namespaces=NS):
#                 if t_node.text and placeholder in t_node.text:
#                     t_node.text = t_node.text.replace(placeholder, "")
#             return

#         # Find insertion index
#         insert_index = list(parent).index(placeholder_para)

#         # Remove the placeholder paragraph
#         parent.remove(placeholder_para)

#         # Insert the extracted XML paragraphs
#         for i, para in enumerate(xml_paragraphs):
#             parent.insert(insert_index + i, para)

#     @staticmethod
#     def _replace_experience_with_xml(root, xml_paragraphs):
#         """
#         Find all experience placeholder paragraphs
#         (INSERT_EXPERIENCE1, INSERT_EXPERIENCE1_RESPONSIBILITIES,
#          INSERT_EXPERIENCE2, INSERT_EXPERIENCE2_RESPONSIBILITIES)
#         and replace them with the extracted XML paragraphs.
#         """
#         # Collect all paragraphs that contain experience placeholders
#         exp_placeholders = [
#             "INSERT_EXPERIENCE1_RESPONSIBILITIES",
#             "INSERT_EXPERIENCE1",
#             "INSERT_EXPERIENCE2_RESPONSIBILITIES",
#             "INSERT_EXPERIENCE2",
#         ]

#         paras_to_remove = []
#         first_para = None
#         parent = None

#         for t_node in root.xpath(".//w:t", namespaces=NS):
#             if not t_node.text:
#                 continue
#             for ph in exp_placeholders:
#                 if ph in t_node.text:
#                     # Walk up to <w:p>
#                     node = t_node
#                     while node is not None:
#                         if node.tag == f"{{{NS['w']}}}p":
#                             if node not in paras_to_remove:
#                                 paras_to_remove.append(node)
#                                 if first_para is None:
#                                     first_para = node
#                                     parent = node.getparent()
#                             break
#                         node = node.getparent()
#                     break

#         if not parent or not first_para:
#             return

#         # Also remove any separator paragraphs between the placeholder paras
#         # (empty paragraphs between the first and last placeholder)
#         if len(paras_to_remove) >= 2:
#             siblings = list(parent)
#             first_idx = siblings.index(paras_to_remove[0])
#             last_idx = siblings.index(paras_to_remove[-1])
#             for idx in range(first_idx, last_idx + 1):
#                 if siblings[idx] not in paras_to_remove:
#                     paras_to_remove.append(siblings[idx])

#         insert_index = list(parent).index(first_para)

#         # Remove all placeholder paragraphs
#         for p in paras_to_remove:
#             if p.getparent() is not None:
#                 p.getparent().remove(p)

#         if not xml_paragraphs:
#             return

#         # Insert the extracted XML paragraphs
#         for i, para in enumerate(xml_paragraphs):
#             parent.insert(insert_index + i, para)

#     @staticmethod
#     def _merge_numbering(extract_dir, numbering_defs):
#         """
#         Merge source numbering definitions (abstractNum + num elements)
#         into the template's word/numbering.xml. Creates the file if it
#         doesn't exist.
#         """
#         W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
#         abstract_elements, num_elements = numbering_defs

#         numbering_xml = extract_dir / "word" / "numbering.xml"

#         if numbering_xml.exists():
#             tree = etree.parse(str(numbering_xml))
#             root = tree.getroot()
#         else:
#             # Create a minimal numbering.xml
#             root = etree.Element(
#                 f"{{{W}}}numbering",
#                 nsmap={"w": W},
#             )
#             tree = etree.ElementTree(root)

#         # Collect existing IDs to avoid duplicates
#         existing_abstract_ids = {
#             el.get(f"{{{W}}}abstractNumId")
#             for el in root.xpath("w:abstractNum", namespaces=NS)
#         }
#         existing_num_ids = {
#             el.get(f"{{{W}}}numId")
#             for el in root.xpath("w:num", namespaces=NS)
#         }

#         for abs_el in abstract_elements:
#             aid = abs_el.get(f"{{{W}}}abstractNumId")
#             if aid not in existing_abstract_ids:
#                 root.append(abs_el)

#         for num_el in num_elements:
#             nid = num_el.get(f"{{{W}}}numId")
#             if nid not in existing_num_ids:
#                 root.append(num_el)

#         tree.write(
#             str(numbering_xml),
#             xml_declaration=True,
#             encoding="UTF-8",
#             standalone="yes",
#         )

#         # Ensure numbering.xml is registered in [Content_Types].xml
#         content_types_path = extract_dir / "[Content_Types].xml"
#         if content_types_path.exists():
#             ct_tree = etree.parse(str(content_types_path))
#             ct_root = ct_tree.getroot()
#             CT_NS = ct_root.nsmap.get(None, "http://schemas.openxmlformats.org/package/2006/content-types")
#             numbering_part = "/word/numbering.xml"
#             already = any(
#                 el.get("PartName") == numbering_part
#                 for el in ct_root.iter(f"{{{CT_NS}}}Override")
#             )
#             if not already:
#                 override = etree.SubElement(ct_root, f"{{{CT_NS}}}Override")
#                 override.set("PartName", numbering_part)
#                 override.set(
#                     "ContentType",
#                     "application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml",
#                 )
#             ct_tree.write(
#                 str(content_types_path),
#                 xml_declaration=True,
#                 encoding="UTF-8",
#                 standalone="yes",
#             )

#         # Ensure numbering.xml is referenced in word/_rels/document.xml.rels
#         rels_path = extract_dir / "word" / "_rels" / "document.xml.rels"
#         if rels_path.exists():
#             rels_tree = etree.parse(str(rels_path))
#             rels_root = rels_tree.getroot()
#             RELS_NS = rels_root.nsmap.get(None, "http://schemas.openxmlformats.org/package/2006/relationships")
#             NUMBERING_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering"
#             already = any(
#                 el.get("Type") == NUMBERING_REL_TYPE
#                 for el in rels_root
#             )
#             if not already:
#                 # Pick an rId that doesn't conflict
#                 existing_ids = {el.get("Id") for el in rels_root}
#                 n = 1
#                 while f"rId{n}" in existing_ids:
#                     n += 1
#                 rel = etree.SubElement(rels_root, f"{{{RELS_NS}}}Relationship")
#                 rel.set("Id", f"rId{n}")
#                 rel.set("Type", NUMBERING_REL_TYPE)
#                 rel.set("Target", "numbering.xml")
#             rels_tree.write(
#                 str(rels_path),
#                 xml_declaration=True,
#                 encoding="UTF-8",
#                 standalone="yes",
#             )

#     @staticmethod
#     def populate_from_xml(
#         template_docx,
#         output_docx,
#         education_xml_paragraphs=None,
#         experience_xml_paragraphs=None,
#         numbering_defs=None,
#     ):
#         """
#         Populate the template by inserting raw XML paragraphs extracted
#         from the source resume directly into the template's placeholder
#         locations. Preserves original formatting.

#         Parameters:
#             template_docx: path to the template .docx
#             output_docx: path for the output .docx
#             education_xml_paragraphs: list of <w:p> etree elements for education
#             experience_xml_paragraphs: list of <w:p> etree elements for experience
#             numbering_defs: tuple (abstract_elements, num_elements) from the
#                             source docx, or None
#         """
#         template_docx = Path(template_docx)
#         output_docx = Path(output_docx)

#         with tempfile.TemporaryDirectory() as tmp:
#             extract_dir = Path(tmp)

#             with zipfile.ZipFile(template_docx) as z:
#                 z.extractall(extract_dir)

#             document_xml = extract_dir / "word" / "document.xml"
#             tree = etree.parse(str(document_xml))
#             root = tree.getroot()

#             # Merge numbering definitions from source into template
#             if numbering_defs is not None:
#                 DocxPopulator._merge_numbering(extract_dir, numbering_defs)

#             document_xml = extract_dir / "word" / "document.xml"
#             tree = etree.parse(str(document_xml))
#             root = tree.getroot()

#             # Insert education XML
#             DocxPopulator._replace_placeholder_with_xml(
#                 root,
#                 "INSERT_EDUCATION",
#                 education_xml_paragraphs or [],
#             )

#             # Clear certificates placeholder
#             DocxPopulator._replace_placeholder_with_xml(
#                 root,
#                 "INSERT_CERTIFICATES",
#                 [],
#             )

#             # Insert experience XML
#             DocxPopulator._replace_experience_with_xml(
#                 root,
#                 experience_xml_paragraphs or [],
#             )

#             tree.write(
#                 str(document_xml),
#                 xml_declaration=True,
#                 encoding="UTF-8",
#                 standalone="yes",
#             )

#             with zipfile.ZipFile(
#                 output_docx, "w", zipfile.ZIP_DEFLATED
#             ) as z:
#                 for file in extract_dir.rglob("*"):
#                     if file.is_file():
#                         z.write(file, file.relative_to(extract_dir))
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
