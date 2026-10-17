from zipfile import ZipFile
from lxml import etree as E
from media_automation.ppt.base import create_4x3_presentation, add_centered_text_slide, add_sermon_title_slide
from media_automation.ppt.scripture import add_scripture_passage_slides
from media_automation.bible.provider import BiblePassage,BibleVerse
from media_automation.ppt.sunday_typography import apply_sunday_typography,NS


def test_reference_typography_preserves_content_and_unselected_slides(tmp_path):
    prs=create_4x3_presentation()
    add_centered_text_slide(prs,'기도\n김한섭')
    add_centered_text_slide(prs,'봉헌기도\n최진용')
    add_sermon_title_slide(prs,'믿음과 상황이 충돌할 때','단 1:8~9')
    add_scripture_passage_slides(prs,BiblePassage('단 1:8~9',(BibleVerse(8,'다니엘은 뜻을 정하여 왕의 음식과 그가 마시는 포도주로 자기를 더럽히지 아니하리라'),)))
    add_centered_text_slide(prs,'원본 찬양 텍스트')
    path=tmp_path/'deck.pptx';prs.save(path)
    with ZipFile(path) as z:before={n:z.read(n) for n in z.namelist()}
    mapping=[dict(kind='text',key=k,start=i,end=i,status=s) for i,k,s in [(1,'기도','rendered'),(2,'봉헌기도','rendered'),(3,'설교 제목','rendered'),(4,'성경 본문','bible_inserted')]]
    assert apply_sunday_typography(path,mapping)==[1,2,3,4]
    with ZipFile(path) as z:
        for name,blob in before.items():
            if name not in [f'ppt/slides/slide{i}.xml' for i in range(1,5)]+['ppt/theme/theme1.xml','ppt/slideMasters/slideMaster1.xml','ppt/presentation.xml']:assert z.read(name)==blob
        theme=E.fromstring(z.read('ppt/theme/theme1.xml'))
        assert theme.xpath('//a:majorFont/a:latin/@typeface',namespaces=NS)==['GyeonggiTitleOTF Medium']
        assert theme.xpath('//a:minorFont/a:ea/@typeface',namespaces=NS)==['GyeonggiTitleOTF Medium']
        for i,sizes in [(1,{'5000'}),(2,{'4800'}),(3,{'4400'}),(4,{'3800','4100'})]:
            x=E.fromstring(z.read(f'ppt/slides/slide{i}.xml'))
            assert set(x.xpath('//a:rPr/@sz',namespaces=NS))==sizes
        x=E.fromstring(z.read('ppt/slides/slide4.xml'))
        assert len(x.findall('.//p:sp',NS))==3
        assert ''.join(x.xpath('//a:t/text()',namespaces=NS)).count('다니엘은')==1
        assert x.xpath('//a:lnSpc/a:spcPts/@val',namespaces=NS)==['5500']


def test_reference_announcements_and_character_spacing(tmp_path):
    prs=create_4x3_presentation()
    for text in ['기도\n김한섭','봉헌기도\n최진용','기도\n김한섭 집사','교회 소식']:
        add_centered_text_slide(prs,text)
    add_sermon_title_slide(prs,'믿음과 상황이 충돌할 때','단 1:8~9')
    path=tmp_path/'detail.pptx';prs.save(path)
    entries=[dict(kind='text',key=key,start=n,end=n,status='rendered') for n,key in enumerate(['기도','봉헌기도','기도','교회 소식','설교 제목'],1)]
    apply_sunday_typography(path,entries)
    with ZipFile(path) as z:
        expected=['기 도 :  김한섭 집사','봉헌기도 : 최진용 형제','기 도 :  김한섭 집사','교  회  소  식']
        for n,text in enumerate(expected,1):
            root=E.fromstring(z.read(f'ppt/slides/slide{n}.xml'))
            assert root.xpath('//a:t/text()',namespaces=NS)==[text]
            assert len(root.findall('.//p:txBody/a:p',NS))==1
            assert root.xpath('//a:pPr/@algn',namespaces=NS)==['ctr']
            assert root.xpath('//a:pPr/a:lnSpc/a:spcPct/@val',namespaces=NS)==['100000']
        root=E.fromstring(z.read('ppt/slides/slide5.xml'))
        assert root.xpath('//a:rPr/@spc',namespaces=NS)==['0','-60']
        assert root.xpath('//a:spcBef/a:spcPts/@val',namespaces=NS)==['800','800']


def test_multi_digit_verse_labels_do_not_wrap(tmp_path):
    prs = create_4x3_presentation()
    numbers = (9, 10, 11, 100)
    for n in numbers:
        add_scripture_passage_slides(prs, BiblePassage(f'시 119:{n}', (
            BibleVerse(n, '줄바꿈 검증용 본문'),)))
    path = tmp_path / 'numbers.pptx'
    prs.save(path)
    apply_sunday_typography(path, [dict(kind='text', key='성경 본문',
        start=1, end=4, status='bible_inserted')])
    with ZipFile(path) as package:
        for slide, number in enumerate(numbers, 1):
            root = E.fromstring(package.read(f'ppt/slides/slide{slide}.xml'))
            label = root.xpath('//p:sp[p:nvSpPr/p:cNvPr[@name="Verse number"]]', namespaces=NS)[0]
            props = label.find('p:txBody/a:bodyPr', NS)
            assert props.get('wrap') == 'none'
            assert props.get('lIns') == props.get('rIns') == '0'
            assert label.xpath('.//a:t/text()', namespaces=NS) == [f'{number}.']
            assert label.xpath('.//a:rPr/@sz', namespaces=NS) == ['4100']
            assert len(root.findall('.//p:sp', NS)) == 3
