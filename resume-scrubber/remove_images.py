import zipfile
import tempfile
from pathlib import Path
from lxml import etree

input_docx = "/Users/cwei1/Desktop/cv_checker_script/resume-parser/resumes/CV-047367 CV for Costello, Lori.docx"
output_docx = "resume_modified.docx"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/package/2006/relationships",
}



IMAGE_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
)

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)

    with zipfile.ZipFile(input_docx, "r") as z:
        z.extractall(tmpdir)

    doc_xml = tmpdir / "word" / "document.xml"

    tree = etree.parse(str(doc_xml))
    root = tree.getroot()

    drawings = root.xpath("//w:drawing", namespaces=NS)
    picts = root.xpath("//w:pict", namespaces=NS)

    print(f"Found {len(drawings)} w:drawing elements")
    print(f"Found {len(picts)} w:pict elements")

    for drawing in drawings:
        parent = drawing.getparent()
        if parent is not None:
            parent.remove(drawing)

    for pict in picts:
        parent = pict.getparent()
        if parent is not None:
            parent.remove(pict)

    tree.write(
        str(doc_xml),
        encoding="UTF-8",
        xml_declaration=True
    )

    """"Remove Images from Header"""
    for header_file in (tmpdir / "word").glob("header*.xml"):
        tree = etree.parse(str(header_file))
        root = tree.getroot()

        drawings = root.xpath("//w:drawing", namespaces=NS)
        picts = root.xpath("//w:pict", namespaces=NS)

        for drawing in drawings:
            parent = drawing.getparent()
            if parent is not None:
                parent.remove(drawing)

        for pict in picts:
            parent = pict.getparent()
            if parent is not None:
                parent.remove(pict)

        tree.write(
            str(header_file),
            encoding="UTF-8",
            xml_declaration=True
        )


    """Remove Images from Footer"""
    for footer_file in (tmpdir / "word").glob("footer*.xml"):
        tree = etree.parse(str(footer_file))
        root = tree.getroot()

        drawings = root.xpath("//w:drawing", namespaces=NS)
        picts = root.xpath("//w:pict", namespaces=NS)

        for drawing in drawings:
            parent = drawing.getparent()
            if parent is not None:
                parent.remove(drawing)

        for pict in picts:
            parent = pict.getparent()
            if parent is not None:
                parent.remove(pict)

        tree.write(
            str(footer_file),
            encoding="UTF-8",
            xml_declaration=True
        )

    """Remove Image Relationships"""
    rels_file = tmpdir / "word" / "_rels" / "document.xml.rels"

    if rels_file.exists():
        rels_tree = etree.parse(str(rels_file))
        rels_root = rels_tree.getroot()

        removed_rels = 0

        for rel in list(rels_root):
            if rel.get("Type") == IMAGE_REL_TYPE:
                rels_root.remove(rel)
                removed_rels += 1

        rels_tree.write(
            str(rels_file),
            encoding="UTF-8",
            xml_declaration=True
        )

        print(f"Removed {removed_rels} image relationships")

    media_dir = tmpdir / "word" / "media"

    removed_files = 0

    if media_dir.exists():
        for media_file in media_dir.iterdir():
            if media_file.is_file():
                media_file.unlink()
                removed_files += 1

    print(f"Removed {removed_files} media files")


    with zipfile.ZipFile(output_docx, "w", zipfile.ZIP_DEFLATED) as z:
        for file in tmpdir.rglob("*"):
            if file.is_file():
                z.write(file, file.relative_to(tmpdir))

print(f"Saved: {output_docx}")