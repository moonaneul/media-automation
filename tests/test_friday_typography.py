from zipfile import ZipFile
from lxml import etree as E
import pytest
from media_automation.ppt.base import create_4x3_presentation, add_centered_text_slide
from media_automation.ppt.friday_typography import apply_friday_typography
from media_automation.ppt.sunday_typography import NS

@pytest.mark.parametrize('zoom,faces',[(True,['나눔스퀘어라운드 ExtraBold','나눔바른고딕 UltraLight','나눔스퀘어 Bold']), (False,['경기천년제목 Bold','경기천년제목 Bold','GyeonggiTitleOTF Medium'])])
def test_friday_reference_typography_preserves_content_geometry_originals_and_media(tmp_path,zoom,faces):
    prs=create_4x3_presentation()
    for text in ['기도할 제목','설교 제목','성경 본문','원본 찬양']:add_centered_text_slide(prs,text)
    path=tmp_path/'friday.pptx';prs.save(path)
    with ZipFile(path) as z:before={n:z.read(n) for n in z.namelist()}
    mapping=[dict(kind='text',key=k,start=i,end=i,status=s) for i,k,s in [(1,'첫 기도 제목','rendered'),(2,'설교 제목','rendered'),(3,'성경 본문','bible_inserted'),(4,'찬양','original_inserted')]]
    assert apply_friday_typography(path,mapping,zoom=zoom)==[1,2,3]
    with ZipFile(path) as z:
        for n,b in before.items():
            if n not in [f'ppt/slides/slide{i}.xml' for i in (1,2,3)]:assert z.read(n)==b
        for i,face in enumerate(faces,1):
            n=f'ppt/slides/slide{i}.xml';a=E.fromstring(before[n]);b=E.fromstring(z.read(n))
            assert b.xpath('//a:rPr/a:ea/@typeface',namespaces=NS)==[face]
            if zoom:
                assert b.xpath('//a:rPr/@sz',namespaces=NS)==[str([3600,4400,3200][i-1])]
                assert b.xpath('//a:rPr/@b',namespaces=NS)==['1']
            else:
                assert a.xpath('//a:rPr/@sz',namespaces=NS)==b.xpath('//a:rPr/@sz',namespaces=NS)
            assert a.xpath('//a:t/text()',namespaces=NS)==b.xpath('//a:t/text()',namespaces=NS)
            assert E.tostring(a.find('.//p:spPr',NS))==E.tostring(b.find('.//p:spPr',NS))
