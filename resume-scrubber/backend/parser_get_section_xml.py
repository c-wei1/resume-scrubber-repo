# import zipfile
# import tempfile
# from pathlib import Path
# from typing import Dict, List, Optional, Set
# from copy import deepcopy

# from lxml import etree

# from parser_get_section import SectionParser

# NS = {
#     "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
#     "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
# }

# W_URI = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
# R_URI = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
# # Relationship types to strip
# IMAGE_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
# HYPERLINK_REL_TYPE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"


# class SectionXmlParser:
#     """
#     Extract raw XML paragraphs (<w:p> elements) grouped by resume section.

#     Uses the same section-identification logic as SectionParser but operates
#     directly on the docx XML so that formatting is preserved.
#     """

#     @classmethod
#     def _get_paragraph_text(cls, p_el) -> str:
#         """Extract plain text from a <w:p> element (top-level text only).
#         Skips text inside nested paragraphs (text boxes)."""
#         P_TAG = f"{{{W_URI}}}p"
#         T_TAG = f"{{{W_URI}}}t"
#         parts = []
#         for t in p_el.iter(T_TAG):
#             # Skip text inside nested paragraphs (text boxes, drawings)
#             parent = t.getparent()
#             nested = False
#             while parent is not None and parent is not p_el:
#                 if parent.tag == P_TAG:
#                     nested = True
#                     break
#                 parent = parent.getparent()
#             if not nested and t.text:
#                 parts.append(t.text)
#         return "".join(parts).strip()

#     @classmethod
#     def _get_full_text(cls, p_el) -> str:
#         """Extract ALL text from a <w:p> element including nested text boxes.
#         Used for section header detection."""
#         T_TAG = f"{{{W_URI}}}t"
#         return "".join(t.text for t in p_el.iter(T_TAG) if t.text).strip()

#     @classmethod
#     def _get_header_candidates(cls, p_el) -> List[str]:
#         """
#         Return candidate texts to check for section headers.

#         Some documents put section headers inside text boxes (drawings)
#         within a paragraph. This method returns:
#         1. The top-level paragraph text
#         2. The text of each nested paragraph (from text boxes)

#         This allows detecting headers even when they're in text boxes,
#         without concatenating duplicates into a single long string.
#         """
#         P_TAG = f"{{{W_URI}}}p"
#         T_TAG = f"{{{W_URI}}}t"

#         candidates = []

#         # Top-level text (excluding nested paragraphs)
#         top_text = cls._get_paragraph_text(p_el)
#         if top_text:
#             candidates.append(top_text)

#         # Text from each nested paragraph (text boxes, drawings)
#         for nested_p in p_el.iter(P_TAG):
#             if nested_p is p_el:
#                 continue
#             # Get direct text of this nested paragraph
#             nested_text = "".join(
#                 t.text for t in nested_p.findall(f".//{T_TAG}")
#                 if t.text
#             ).strip()
#             if nested_text and nested_text not in candidates:
#                 candidates.append(nested_text)

#         return candidates

#     @classmethod
#     def _sanitize_paragraph(cls, p_el) -> etree._Element:
#         """
#         Clean a <w:p> element so it can be safely inserted into a
#         different docx without causing 'unreadable content' errors.

#         1. Strip style references (w:pStyle, w:rStyle) — the target
#            template may not define the same style IDs.
#         2. Remove hyperlink wrappers — keep the visible text runs but
#            drop the <w:hyperlink> element (which carries an r:id that
#            won't resolve in the target).
#         3. Remove drawing / image elements that reference relationships
#            (r:id) in the source document.
#         4. Remove dangling r:id attributes from <w:r> or other elements.
#         """
#         # --- 1. Strip paragraph and run style references ---
#         for pStyle in p_el.xpath(".//w:pStyle", namespaces=NS):
#             pStyle.getparent().remove(pStyle)
#         for rStyle in p_el.xpath(".//w:rStyle", namespaces=NS):
#             rStyle.getparent().remove(rStyle)

#         # --- 2. Unwrap hyperlinks: keep child runs, remove wrapper ---
#         for hl in p_el.xpath(".//w:hyperlink", namespaces=NS):
#             parent = hl.getparent()
#             if parent is None:
#                 continue
#             idx = list(parent).index(hl)
#             children = list(hl)
#             for child in children:
#                 hl.remove(child)
#                 parent.insert(idx, child)
#                 idx += 1
#             parent.remove(hl)

#         # --- 3. Remove drawings / images that carry relationship refs ---
#         for drawing in p_el.xpath(".//w:drawing", namespaces=NS):
#             # If the drawing has text (e.g. text box), keep it but
#             # strip image-specific children; otherwise remove entirely.
#             has_text = bool(drawing.xpath(".//*[local-name()='t']"))
#             if has_text:
#                 for node in list(drawing.iter()):
#                     localname = etree.QName(node).localname
#                     if localname in ("blip", "blipFill", "imagedata"):
#                         p = node.getparent()
#                         if p is not None:
#                             p.remove(node)
#             else:
#                 drawing.getparent().remove(drawing)

#         for pict in p_el.xpath(".//w:pict", namespaces=NS):
#             has_text = bool(pict.xpath(".//*[local-name()='t']"))
#             if not has_text:
#                 pict.getparent().remove(pict)

#         # --- 4. Remove any remaining r:id attributes (dangling refs) ---
#         R_ID = f"{{{R_URI}}}id"
#         for el in p_el.iter():
#             if R_ID in el.attrib:
#                 del el.attrib[R_ID]

#         return p_el

#     @classmethod
#     def _collect_num_ids(cls, paragraphs: List[etree._Element]) -> Set[str]:
#         """Return the set of w:numId values used by the given paragraphs."""
#         num_ids: Set[str] = set()
#         for p in paragraphs:
#             for numId in p.xpath(".//w:numId", namespaces=NS):
#                 val = numId.get(f"{{{W_URI}}}val")
#                 if val and val != "0":
#                     num_ids.add(val)
#         return num_ids

#     @classmethod
#     def _extract_numbering_defs(
#         cls, docx_path: Path, num_ids: Set[str]
#     ) -> Optional[etree._Element]:
#         """
#         Extract <w:abstractNum> and <w:num> definitions from the source
#         docx's word/numbering.xml for the given numId values.
#         Returns the full numbering root element (pruned to only the
#         referenced entries), or None if no numbering.xml exists.
#         """
#         with tempfile.TemporaryDirectory() as tmp:
#             extract_dir = Path(tmp)
#             with zipfile.ZipFile(docx_path) as z:
#                 z.extractall(extract_dir)
#             numbering_xml = extract_dir / "word" / "numbering.xml"
#             if not numbering_xml.exists():
#                 return None
#             tree = etree.parse(str(numbering_xml))
#             root = tree.getroot()

#         # Find <w:num> elements whose w:numId matches
#         needed_abstract_ids: Set[str] = set()
#         num_elements = []
#         for num_el in root.xpath("w:num", namespaces=NS):
#             nid = num_el.get(f"{{{W_URI}}}numId")
#             if nid in num_ids:
#                 num_elements.append(deepcopy(num_el))
#                 # Find the abstractNumId reference
#                 for absRef in num_el.xpath("w:abstractNumId", namespaces=NS):
#                     val = absRef.get(f"{{{W_URI}}}val")
#                     if val:
#                         needed_abstract_ids.add(val)

#         abstract_elements = []
#         for abs_el in root.xpath("w:abstractNum", namespaces=NS):
#             aid = abs_el.get(f"{{{W_URI}}}abstractNumId")
#             if aid in needed_abstract_ids:
#                 abstract_elements.append(deepcopy(abs_el))

#         if not num_elements and not abstract_elements:
#             return None

#         return abstract_elements, num_elements

#     @classmethod
#     def extract_sections_xml(cls, docx_path) -> Dict[str, List[etree._Element]]:
#         """
#         Parse a docx file and return a dict mapping section names
#         (e.g. "education", "experience", "other") to lists of sanitized
#         <w:p> elements (deep copies) belonging to that section.

#         The returned dict also contains a special key "_numbering" whose
#         value is a tuple (abstract_elements, num_elements) of numbering
#         definitions needed by the extracted paragraphs, or None.
#         """
#         docx_path = Path(docx_path)

#         with tempfile.TemporaryDirectory() as tmp:
#             extract_dir = Path(tmp)
#             with zipfile.ZipFile(docx_path) as z:
#                 z.extractall(extract_dir)

#             document_xml = extract_dir / "word" / "document.xml"
#             tree = etree.parse(str(document_xml))
#             root = tree.getroot()

#         # Collect direct body <w:p> children (the content flow)
#         body = root.find(f"{{{W_URI}}}body")
#         if body is None:
#             return {}

#         P_TAG = f"{{{W_URI}}}p"
#         paragraphs = [child for child in body if child.tag == P_TAG]

#         # For each paragraph, collect candidate texts for header detection.
#         # Some documents put section headers inside text boxes within a
#         # paragraph, so we check both top-level text and nested texts.
#         all_candidates = [cls._get_header_candidates(p) for p in paragraphs]

#         # Build line_counts from deduplicated candidate texts.
#         # Text-box formatting can repeat header text; deduplication
#         # ensures the uniqueness check still passes for real headers.
#         seen_texts = set()
#         unique_texts = []
#         for candidates in all_candidates:
#             for t in candidates:
#                 if t and t not in seen_texts:
#                     seen_texts.add(t)
#                     unique_texts.append(t)
#         full_text = "\n".join(unique_texts)
#         line_counts = SectionParser._build_line_counts(full_text)

#         # Walk paragraphs and assign to sections
#         sections: Dict[str, List[etree._Element]] = {}
#         current_section = "header"
#         current_paras: List[etree._Element] = []

#         for p_el, candidates in zip(paragraphs, all_candidates):
#             # Check if any candidate text is a section header
#             header_key = None
#             header_is_nested = False
#             top_text = cls._get_paragraph_text(p_el)

#             for text in candidates:
#                 if text and SectionParser.is_section_header(text, line_counts):
#                     header_key = SectionParser.match_section_key(text, line_counts) or "other"
#                     # Header is "nested" if it's not the top-level text
#                     header_is_nested = (text != top_text)
#                     break

#             if header_key is not None:
#                 # If the header comes from a nested text box but the
#                 # paragraph also has top-level content (e.g. school info),
#                 # include the sanitized paragraph in the current section
#                 # before switching. Strip all nested containers (text boxes,
#                 # drawings) so only the top-level text remains.
#                 if header_is_nested and top_text:
#                     clean_para = cls._sanitize_paragraph(deepcopy(p_el))
#                     # Remove any remaining elements that contain nested <w:p>
#                     # (text boxes, drawings with text) to keep only top-level text
#                     P_TAG = f"{{{W_URI}}}p"
#                     for nested_p in list(clean_para.iter(P_TAG)):
#                         if nested_p is clean_para:
#                             continue
#                         # Walk up to find the removable ancestor
#                         node = nested_p
#                         while node.getparent() is not None and node.getparent() is not clean_para:
#                             node = node.getparent()
#                         if node.getparent() is clean_para:
#                             clean_para.remove(node)
#                     current_paras.append(clean_para)

#                 # Save current section and switch
#                 if current_paras:
#                     sections.setdefault(current_section, []).extend(current_paras)
#                 current_section = header_key
#                 current_paras = []
#             else:
#                 # Detect publications bleeding into experience section
#                 if (
#                     current_section == "experience"
#                     and top_text
#                     and SectionParser._looks_like_publication(top_text)
#                 ):
#                     if current_paras:
#                         sections.setdefault(current_section, []).extend(current_paras)
#                     current_section = "other"
#                     current_paras = []

#                 # Deep-copy and sanitize before storing
#                 clean_para = cls._sanitize_paragraph(deepcopy(p_el))
#                 current_paras.append(clean_para)

#         # Save last section
#         if current_paras:
#             sections.setdefault(current_section, []).extend(current_paras)

#         # Collect numbering IDs used across all extracted paragraphs
#         all_paras = []
#         for key, paras in sections.items():
#             all_paras.extend(paras)
#         num_ids = cls._collect_num_ids(all_paras)
#         if num_ids:
#             sections["_numbering"] = cls._extract_numbering_defs(
#                 docx_path, num_ids
#             )

#         return sections
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

        if referenced_num_ids is None:
            return all_abstract, all_num

        # Filter num elements
        wanted_num: List[etree._Element] = []
        wanted_abstract_ids: Set[str] = set()

        for num_el in all_num:
            nid = num_el.get(f"{{{W_URI}}}numId")
            if nid in referenced_num_ids:
                wanted_num.append(num_el)
                for abs_ref in num_el.xpath(
                    "w:abstractNumId", namespaces=NS
                ):
                    aid = abs_ref.get(f"{{{W_URI}}}val")
                    if aid:
                        wanted_abstract_ids.add(aid)

        wanted_abstract = [
            a for a in all_abstract
            if a.get(f"{{{W_URI}}}abstractNumId") in wanted_abstract_ids
        ]
        return wanted_abstract, wanted_num

    # ─────────────────────────────────────────────────────────────
    # Convenience: one-shot builder from source docx
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
