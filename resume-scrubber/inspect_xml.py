
import zipfile
from xml.dom import minidom

with zipfile.ZipFile("/Users/cwei1/Desktop/cv_checker_script/resumes/CV-047367 CV for Costello, Lori.docx") as z:
    xml = z.read("word/document.xml")

pretty_xml = minidom.parseString(xml).toprettyxml(indent="  ")
print(pretty_xml)
