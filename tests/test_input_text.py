import pytest
from media_automation.input_text import clean_leading_marks
from media_automation.web.original.production_order import build_order
from media_automation.web.original.bible_connection import resolve
from media_automation.ppt.friday_reference import prayer_body_text

@pytest.mark.parametrize('prefix',['', '   ', '- ', '. ', '- . • ', '\u200b　＊：'])
@pytest.mark.parametrize('service',['wednesday','friday','sunday'])
def test_shared_input_cleanup_preserves_text_and_numbering(prefix,service):
    fields={key:{'state':'VALUE','value':prefix+text} for key,text in [
        ('기도 제목 1','영적인 성장.'),('기도 내용 1','우리 안에 거하시는 성령. (기도)'),
        ('추가 말씀 1','사 43:21, 왕상 8:27, 히 10:19~20')]}
    order=build_order([['기도',list(fields)]],fields,service)
    blocks={b['key']:b for b in order if b['kind']!='blank'}
    assert blocks['기도 제목 1']['content']=='1. 영적인 성장.'
    assert blocks['기도 내용 1']['content']=='우리 안에 거하시는 성령. (기도)'
    assert blocks['추가 말씀 1']['content']=='사 43:21, 왕상 8:27, 히 10:19~20'
    assert fields['기도 내용 1']['value']==prefix+'우리 안에 거하시는 성령. (기도)'

def test_reference_lookup_cleans_each_address_and_keeps_ranges(tmp_path):
    import json
    sources=tmp_path/'sources';sources.mkdir()
    # Use an explicit local validated fixture, never substitute previous-week text.
    (sources/'test.yaml').write_text('translation: 개역개정\nvalidated: true\npassages:\n  test:\n    reference: 히 10:19~20\n    verses:\n      19: 첫 절\n      20: 둘째 절\n',encoding='utf-8')
    blocks=[dict(kind='input',state='VALUE',key='추가 말씀 1',content=' - 히 10:19, . 히 10:20')]
    result=resolve(blocks,source_dir=sources,provided_file=tmp_path/'missing.json')
    assert [u['start_verse'] for u in result['추가 말씀 1']['units']]==[19,20]

def test_prayer_prefix_is_added_once_and_meaningful_punctuation_survives():
    assert prayer_body_text(' . 첫 문장.\n - . 둘째 (문장).')=='- 첫 문장.\n- 둘째 (문장).'
    assert clean_leading_marks('(요일 2:12~17)')=='(요일 2:12~17)'
    assert clean_leading_marks('1. 기도')=='1. 기도'
    assert clean_leading_marks('“기도”')=='“기도”'
