
import zipfile
from xml.dom import minidom

with zipfile.ZipFile("/Users/cwei1/Downloads/FRM-11110-CarolineWei.docx") as z:
    xml = z.read("word/document.xml")

pretty_xml = minidom.parseString(xml).toprettyxml(indent="  ")
print(pretty_xml)
