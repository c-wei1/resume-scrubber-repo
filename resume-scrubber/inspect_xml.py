import zipfile
from lxml import etree

with zipfile.ZipFile("/Users/cwei1/Library/CloudStorage/OneDrive-GileadSciences/Desktop/cv_checker_script/resumes/L.Wilkins Resume 25-Jul-2024.docx") as z:
    xml = z.read("word/document.xml")

root = etree.fromstring(xml)

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
}

for p in root.xpath("//w:p", namespaces=NS):
    text = "".join(
        t.text or ""
        for t in p.xpath(".//w:t", namespaces=NS)
    ).strip()

    if text:
        print(text)