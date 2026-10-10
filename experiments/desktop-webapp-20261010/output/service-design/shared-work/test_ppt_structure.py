import tempfile,unittest
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from zoom_media import normalize_layout_ids

class StructureTests(unittest.TestCase):
    def test_duplicate_color_and_misordered_run_properties(self):
        p='http://schemas.openxmlformats.org/presentationml/2006/main';a='http://schemas.openxmlformats.org/drawingml/2006/main'
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'test.pptx'
            with ZipFile(file,'w') as z:
                z.writestr('ppt/presentation.xml',f'<p:presentation xmlns:p="{p}"/>')
                z.writestr('ppt/slides/slide1.xml',f'<p:sld xmlns:p="{p}" xmlns:a="{a}"><a:rPr><a:latin typeface="Font"/><a:solidFill><a:srgbClr val="FFFF00"/><a:srgbClr val="FFFFFF"/></a:solidFill></a:rPr></p:sld>')
            normalize_layout_ids(file)
            with ZipFile(file) as z:root=E.fromstring(z.read('ppt/slides/slide1.xml'))
            props=root[0]
            self.assertEqual([E.QName(c).localname for c in props],['solidFill','latin'])
            self.assertEqual(len(props[0]),1)
            self.assertEqual(props[0][0].get('val'),'FFFF00')

if __name__=='__main__':unittest.main()
