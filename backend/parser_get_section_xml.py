"""
SectionXmlParser
================

Thin helper that produces the XML fragments needed to populate the
template. It does NOT re-implement text extraction or section
detection — those come from TextExtractor + SectionParser so both
pipelines see the same segmentation.

Responsibilities:
    1. Given a section's (text, <w:p>) pairs, hand back deep-copied
       <w:p> elements ready to drop into the template.
    2. Extract numbering definitions (abstractNum + num) from the
       source docx so bullet lists survive the trip into the template.
    3. Extract style definitions the source paragraphs reference
       (optional, best-effort).

There is deliberately no header-detection logic in here.
"""

import zipfile
from pathlib import Path
from typing import List, Optional, Set, Tuple

from lxml import etree

from parser_get_section import Pair, SectionParser


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}
W_URI = NS["w"]


class SectionXmlParser:
    """Produces XML fragments derived from the SectionParser output."""

    # ─────────────────────────────────────────────────────────────
    # Paragraph sanitization
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def _sanitize_paragraph(p_el: etree._Element) -> etree._Element:
        """
        Clean a <w:p> element for safe insertion into a different docx.

        1. Remove images/drawings (they reference r:id that won't exist
           in the target).
        2. Unwrap hyperlinks — keep visible text, drop the wrapper.
        3. Strip dangling r:id attributes.
        4. Strip style references (pStyle, rStyle) — the target template
           may not have the same style definitions.
        5. Convert numbered lists to bullets (change numId references so
           downstream _merge_numbering produces bullets, not numbers).
        """
        R_ID = f"{{{NS['r']}}}id"

        # --- 1. Remove drawings and images ---
        for drawing in p_el.xpath(".//w:drawing", namespaces=NS):
            # Keep text boxes, remove everything else
            has_text = bool(drawing.xpath(".//*[local-name()='t']"))
            if not has_text:
                parent = drawing.getparent()
                if parent is not None:
                    parent.remove(drawing)

        for pict in p_el.xpath(".//w:pict", namespaces=NS):
            has_text = bool(pict.xpath(".//*[local-name()='t']"))
            if not has_text:
                parent = pict.getparent()
                if parent is not None:
                    parent.remove(pict)

        # --- 2. Unwrap hyperlinks ---
        for hl in p_el.xpath(".//w:hyperlink", namespaces=NS):
            parent = hl.getparent()
            if parent is None:
                continue
            idx = list(parent).index(hl)
            children = list(hl)
            for child in children:
                hl.remove(child)
                parent.insert(idx, child)
                idx += 1
            parent.remove(hl)

        # --- 3. Remove dangling r:id attributes ---
        for el in p_el.iter():
            if R_ID in el.attrib:
                del el.attrib[R_ID]

        # --- 4. Strip style references ---
        for pStyle in p_el.xpath(".//w:pStyle", namespaces=NS):
            pStyle.getparent().remove(pStyle)
        for rStyle in p_el.xpath(".//w:rStyle", namespaces=NS):
            rStyle.getparent().remove(rStyle)

        return p_el

    @staticmethod
    def _convert_numbering_to_bullets(
        paragraphs: List[etree._Element],
        numbering_defs: Tuple[List[etree._Element], List[etree._Element]],
    ) -> Tuple[List[etree._Element], List[etree._Element]]:
        """
        Convert numbered/bulleted list paragraphs to plain paragraphs
        with a bullet character prepended. Removes <w:numPr> so no
        numbering.xml dependency is needed in the target template.

        Modifies paragraphs in-place and returns empty numbering defs
        (since numbering is no longer needed).
        """
        BULLET = "\u2022 "  # • followed by space

        for p in paragraphs:
            # Find numPr inside pPr
            for num_pr in p.xpath(".//w:numPr", namespaces=NS):
                num_pr.getparent().remove(num_pr)

                # Prepend bullet to the first <w:t> in this paragraph
                first_t = p.find(f".//{{{W_URI}}}t")
                if first_t is not None and first_t.text:
                    first_t.text = BULLET + first_t.text
                elif first_t is not None:
                    first_t.text = BULLET

        # No numbering defs needed anymore
        return [], []

    # ─────────────────────────────────────────────────────────────
    # Section paragraphs
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def section_paragraphs(
        section_pairs: List[Pair],
    ) -> List[etree._Element]:
        """
        Return deep-copied, sanitized <w:p> elements for a section's pairs.
        Filters out any pairs whose xml side is None (e.g. text-only
        fixtures used in tests).
        """
        result = []
        for _, xml in section_pairs:
            if xml is None:
                continue
            p = etree.fromstring(etree.tostring(xml))
            p = SectionXmlParser._sanitize_paragraph(p)
            result.append(p)
        return result

    # ─────────────────────────────────────────────────────────────
    # Numbering carry-over
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def collect_referenced_num_ids(
        paragraphs: List[etree._Element],
    ) -> Set[str]:
        """Every w:numId referenced by the given paragraphs."""
        num_ids: Set[str] = set()
        for p in paragraphs:
            for num_pr in p.xpath(".//w:numPr/w:numId", namespaces=NS):
                nid = num_pr.get(f"{{{W_URI}}}val")
                if nid:
                    num_ids.add(nid)
        return num_ids

    @staticmethod
    def _force_abstract_num_to_bullets(
        abstract_num: etree._Element,
    ) -> None:

        for lvl in abstract_num.xpath(".//w:lvl", namespaces=NS):

            num_fmt = lvl.find(f"{{{W_URI}}}numFmt")
            if num_fmt is not None:
                num_fmt.set(f"{{{W_URI}}}val", "bullet")

            lvl_text = lvl.find(f"{{{W_URI}}}lvlText")
            if lvl_text is not None:
                lvl_text.set(f"{{{W_URI}}}val", "•")

            # Ensure Word renders the bullet properly
            rpr = lvl.find(f"{{{W_URI}}}rPr")

            if rpr is None:
                rpr = etree.SubElement(
                    lvl,
                    f"{{{W_URI}}}rPr"
                )

            fonts = rpr.find(f"{{{W_URI}}}rFonts")

            if fonts is None:
                fonts = etree.SubElement(
                    rpr,
                    f"{{{W_URI}}}rFonts"
                )

            fonts.set(f"{{{W_URI}}}ascii", "Symbol")
            fonts.set(f"{{{W_URI}}}hAnsi", "Symbol")

    @staticmethod
    def extract_numbering(
        source_docx: Path,
        referenced_num_ids: Optional[Set[str]] = None,
    ) -> Tuple[List[etree._Element], List[etree._Element]]:
        """
        Read word/numbering.xml from the source and return
        (abstract_num_elements, num_elements).

        If `referenced_num_ids` is supplied, only those num definitions
        (and their transitively referenced abstractNums) are returned.
        Otherwise, everything is returned.

        Any extracted abstract numbering definitions are converted
        to bullet lists so ordered lists become unordered lists when
        inserted into the target template.
        """
        try:
            with zipfile.ZipFile(str(source_docx)) as z:
                if "word/numbering.xml" not in z.namelist():
                    return [], []

                data = z.read("word/numbering.xml")

        except (KeyError, zipfile.BadZipFile):
            return [], []

        root = etree.fromstring(data)

        all_num = root.xpath("w:num", namespaces=NS)
        all_abstract = root.xpath("w:abstractNum", namespaces=NS)

        # If no filtering requested, use all numbering definitions
        if referenced_num_ids is None:

            converted_abstracts = []

            for abstract in all_abstract:
                abstract_copy = etree.fromstring(
                    etree.tostring(abstract)
                )

                SectionXmlParser._force_abstract_num_to_bullets(
                    abstract_copy
                )

                converted_abstracts.append(abstract_copy)

            return converted_abstracts, all_num

        # ----------------------------------------------------------
        # Filter num elements actually referenced by this section
        # ----------------------------------------------------------

        wanted_num: List[etree._Element] = []
        wanted_abstract_ids: Set[str] = set()

        for num_el in all_num:

            nid = num_el.get(f"{{{W_URI}}}numId")

            if nid in referenced_num_ids:

                wanted_num.append(
                    etree.fromstring(etree.tostring(num_el))
                )

                for abs_ref in num_el.xpath(
                    "w:abstractNumId",
                    namespaces=NS,
                ):
                    aid = abs_ref.get(f"{{{W_URI}}}val")

                    if aid:
                        wanted_abstract_ids.add(aid)

        # ----------------------------------------------------------
        # Collect matching abstract numbering definitions
        # ----------------------------------------------------------

        wanted_abstract: List[etree._Element] = []

        for abstract in all_abstract:

            abstract_id = abstract.get(
                f"{{{W_URI}}}abstractNumId"
            )

            if abstract_id in wanted_abstract_ids:

                abstract_copy = etree.fromstring(
                    etree.tostring(abstract)
                )

                SectionXmlParser._force_abstract_num_to_bullets(
                    abstract_copy
                )

                wanted_abstract.append(abstract_copy)

        return wanted_abstract, wanted_num

    # ─────────────────────────────────────────────────────────────
    # Builder from source docx
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def build_for_section(
        source_docx: Path,
        section_pairs: List[Pair],
    ) -> Tuple[List[etree._Element], Tuple[List[etree._Element], List[etree._Element]]]:
        """
        Produce (xml_paragraphs, (abstract_defs, num_defs)) for a single
        section, filtered to the numbering definitions actually
        referenced by those paragraphs.
        """
        paragraphs = SectionXmlParser.section_paragraphs(section_pairs)
        num_ids = SectionXmlParser.collect_referenced_num_ids(paragraphs)
        numbering_defs = SectionXmlParser.extract_numbering(
            source_docx, num_ids
        )
        return paragraphs, numbering_defs
