"""Long-content regressions: preserve complete text or fail before publishing."""
from dataclasses import replace
from zipfile import ZipFile
import pytest
from lxml import etree as E
from media_automation.ppt.base import create_4x3_presentation
from media_automation.ppt.scripture import add_scripture_passage_slides
from media_automation.ppt.sunday_typography import apply_sunday_typography, NS
from media_automation.bible.provider import BiblePassage, BibleVerse
from media_automation.bulletin.document import BulletinDocument, BulletinCoverPage, BulletinWorshipPage, BulletinCellGroupPage, BulletinNewsPage
from media_automation.bulletin.original_design import render_original_bulletin


def test_long_verse_survives_final_font_application(tmp_path):
    text = '그 때 시완월 곧 삼월 이십삼일에 왕의 서기관이 소집되고 모르드개가 시키는 대로 조서를 써서 인도로부터 구스까지의 백이십칠 지방 유다인과 대신과 지방관과 관원에게 전할새 각 지방의 문자와 각 민족의 언어와 유다인의 문자와 언어로 쓰되'
    prs = create_4x3_presentation()
    add_scripture_passage_slides(prs, BiblePassage('에 8:9', (BibleVerse(9, text),)))
    path = tmp_path/'long.pptx'; prs.save(path)
    apply_sunday_typography(path, [dict(kind='scripture',key='성경 본문',start=1,end=1,status='bible_inserted')])
    with ZipFile(path) as z:
        root = E.fromstring(z.read('ppt/slides/slide1.xml'))
    body = root.xpath('//p:sp[p:txBody/a:p/a:r/a:rPr[@sz < 4100]]', namespaces=NS)[-1]
    actual = ''.join(body.xpath('.//a:t/text()', namespaces=NS))
    assert ''.join(actual.split()) == ''.join(text.split())
    sizes = [int(v)/100 for v in body.xpath('.//a:rPr/@sz', namespaces=NS)]
    assert min(sizes) >= 24 and max(sizes) < 41
    leading = int(body.xpath('.//a:spcPts/@val', namespaces=NS)[0])/100
    assert (len(body.findall('.//a:br', NS))+1)*leading <= 330


@pytest.mark.parametrize('field,label', [('sermon_title','설교 제목'),('news','교회 소식'),('question','목장 질문'),('schedule','월간 일정')])
def test_bulletin_overflow_identifies_field_without_output(tmp_path, field, label):
    doc = BulletinDocument(BulletinCoverPage('13-41','2026년 10월 11일'), BulletinWorshipPage(), BulletinCellGroupPage(), BulletinNewsPage((), ()))
    long = '공동체가 함께 기도하며 하나님의 말씀을 나눕니다. '*40
    if field=='sermon_title':doc=replace(doc,worship=replace(doc.worship,sermon_title=long))
    elif field=='question':doc=replace(doc,cell_group=replace(doc.cell_group,questions=(long,)))
    elif field=='schedule':doc=replace(doc,news=replace(doc.news,monthly_schedule=(('11일',long),)))
    else:doc=replace(doc,news=replace(doc.news,church_news=(long,)))
    path=tmp_path/'overflow.pdf'
    with pytest.raises(ValueError,match=label):render_original_bulletin(doc,path)
    assert not path.exists()


def test_serving_table_uses_same_font_for_reference_and_changed_names(tmp_path):
    import pymupdf
    doc=BulletinDocument(BulletinCoverPage('13-41','2026년 10월 11일'),BulletinWorshipPage(first_service_prayer='인도자',second_service_prayer='문하늘',first_service_offering_prayer='임정화',second_service_offering_prayer='임은솔',next_week_first_service_prayer='인도자',next_week_second_service_prayer='위윤기',next_week_first_service_offering_prayer='신무순',next_week_second_service_offering_prayer='김도형'),BulletinCellGroupPage(),BulletinNewsPage((),()))
    path=tmp_path/'fonts.pdf';render_original_bulletin(doc,path)
    pdf=pymupdf.open(path)
    spans=[s for b in pdf[1].get_text('dict')['blocks'] for line in b.get('lines',[]) for s in line['spans'] if 407<=s['bbox'][1]<=469 and 107<=s['bbox'][0]<214]
    names={'인도자','문하늘','임정화','임은솔','위윤기','신무순','김도형'}
    found=[s for s in spans if s['text'].strip() in names]
    assert names <= {s['text'].strip() for s in found}
    assert len({(s['font'],round(s['size'],2)) for s in found})==1
