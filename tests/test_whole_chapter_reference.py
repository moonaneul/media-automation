import json
import pytest
from media_automation.web.original.bible_connection import resolve, expand_chapter_reference


@pytest.mark.parametrize('reference',['행 27~28장','사도행전 27-28장','행27～28장'])
def test_explicit_whole_chapter_range(reference,tmp_path):
    raw={f'행{ch}:{v}':f'연결 검증 {ch}장 {v}절' for ch,end in [(27,44),(28,31)] for v in range(1,end+1)}
    file=tmp_path/'bible.json';file.write_text(json.dumps(raw,ensure_ascii=False))
    result=resolve([dict(kind='input',key='성경 본문',state='VALUE',content=reference)],
                   source_dir=tmp_path/'checked',provided_file=file)['성경 본문']
    assert len(result['units'])==75
    assert result['units'][0]['start_verse']==1
    assert result['units'][43]['start_verse']==44
    assert result['units'][44]['passage_reference']=='행 28:1~31'
    assert result['units'][-1]['start_verse']==31


@pytest.mark.parametrize('missing',['행27:1','행27:20','행28:31'])
def test_incomplete_chapter_is_not_silently_truncated(missing,tmp_path):
    raw={f'행{ch}:{v}':'연결 검증' for ch,end in [(27,44),(28,31)] for v in range(1,end+1)}
    del raw[missing]
    file=tmp_path/'bible.json';file.write_text(json.dumps(raw))
    result=resolve([dict(kind='input',key='성경 본문',state='VALUE',content='행 27~28장')],
                   source_dir=tmp_path/'checked',provided_file=file)['성경 본문']
    assert result['units']==[]
    assert '장·절이 없습니다' in result['error']


def test_unknown_chapter_endpoint_requires_explicit_verses():
    with pytest.raises(ValueError,match='마지막 절'):
        expand_chapter_reference('요 4장')
