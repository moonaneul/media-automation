"""Human-confirmed Korean Bible verses are reusable only as exact-text receipts.

No copyrighted Bible verse is included in fixtures, and no official source is
claimed without the required human comparison.
"""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from media_automation.web.original.bible_connection import resolve
from media_automation.web.original.bible_review_cache import (
    apply_review_receipts, unit_fingerprint, units_for_manual_confirmation,
)
from media_automation.web.original.generation import (
    SUNDAY_TYPOGRAPHY_VERSION, render_configuration,
)
from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore


def source_with_passages(tmp_path, refs):
    path=tmp_path/'provided.json'
    path.write_text(json.dumps(refs,ensure_ascii=False),encoding='utf-8')
    return path


def read_block(path, source_dir, reference='요 3:16',key='성경 본문'):
    return resolve([dict(kind='input',state='VALUE',key=key,content=reference)],
                   source_dir=source_dir,provided_file=path)


def test_no_prior_receipt_never_claims_automatic_bible_validation(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    file=source_with_passages(tmp_path,{'요3:16':'독립된 성경 본문이 아닌 검사 문장'})
    bible=apply_review_receipts(store,read_block(file,tmp_path/'no-source'))
    assert bible['성경 본문']['text_review_pending'] is True
    assert not bible['성경 본문']['source_validated']
    assert not bible['성경 본문'].get('previous_manual_review')


def test_verified_once_exactly_identical_unit_reused_on_future_worship(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    file=source_with_passages(tmp_path,{'요3:16':'검수 기능을 위한 테스트 문장'})
    bible=read_block(file,tmp_path/'no-source')
    checked=units_for_manual_confirmation(bible,['성경 본문:bible_review'])
    assert len(checked)==1
    store.record_bible_review_receipts(checked,date='2026-10-18',
                                       service='sunday',file_id='a'*32)
    later=apply_review_receipts(store,read_block(file,tmp_path/'no-source'))
    assert later['성경 본문']['text_review_pending'] is False
    assert later['성경 본문']['previous_manual_review'] is True
    assert later['성경 본문']['source_validated'] is False
    # The cache is independent of week or section label, never weekly-role data.
    other=apply_review_receipts(store,read_block(file,tmp_path/'no-source',key='추가 말씀 1'))
    assert other['추가 말씀 1']['text_review_pending'] is False


def test_any_source_text_change_invalidates_prior_review(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    file=source_with_passages(tmp_path,{'요3:16':'검수 기능 시험 문장'})
    checked=units_for_manual_confirmation(
        read_block(file,tmp_path/'none'),['성경 본문:bible_review'])
    store.record_bible_review_receipts(checked,date='2026-10-18',
                                       service='sunday',file_id='a'*32)
    file.write_text(json.dumps({'요3:16':'검수 기능 시험 문장!'},ensure_ascii=False),encoding='utf-8')
    later=apply_review_receipts(store,read_block(file,tmp_path/'none'))
    assert later['성경 본문']['text_review_pending'] is True


def test_all_verses_required_for_range_and_combined_unit_cannot_be_split(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    file=source_with_passages(tmp_path,{'요3:16':'첫째 시험','요3:17':'둘째 시험'})
    first=read_block(file,tmp_path/'none')
    checked=units_for_manual_confirmation(first,['성경 본문:bible_review'])
    store.record_bible_review_receipts(checked,date='2026-10-18',
                                       service='sunday',file_id='a'*32)
    full=apply_review_receipts(store,read_block(file,tmp_path/'none',reference='요 3:16~17'))
    assert full['성경 본문']['text_review_pending'] is True
    both=units_for_manual_confirmation(read_block(file,tmp_path/'none',reference='요 3:16~17'),
                                       ['성경 본문:bible_review'])
    store.record_bible_review_receipts(both,date='2026-10-18',
                                       service='sunday',file_id='a'*32)
    assert apply_review_receipts(store,read_block(file,tmp_path/'none',reference='요 3:16~17'))[
        '성경 본문']['text_review_pending'] is False

    combined=source_with_passages(tmp_path,{'신6:18~19':'두 절이 결합된 시험 문장'})
    part=read_block(combined,tmp_path/'none',reference='신 6:19')
    assert not part['성경 본문']['units']
    assert 'error' in part['성경 본문']


def test_no_source_reference_or_unit_number_can_impersonate_a_receipt(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    source=source_with_passages(tmp_path,{'요3:16':'같은 문장','요3:17':'같은 문장'})
    confirmed=units_for_manual_confirmation(read_block(source,tmp_path/'none'),
                                            ['성경 본문:bible_review'])
    store.record_bible_review_receipts(confirmed,date='2026-10-18',
                                       service='sunday',file_id='a'*32)
    different=apply_review_receipts(store,read_block(source,tmp_path/'none',reference='요 3:17'))
    assert different['성경 본문']['text_review_pending'] is True


def test_display_substitution_is_distinct_from_source_proof(tmp_path):
    from media_automation.ppt.scripture import _display_bible_text
    store=WorkStore(tmp_path/'work.db')
    file=source_with_passages(tmp_path,{'요3:16':'세례 검증용 임의 문자열'})
    assert _display_bible_text('세례 검증용 임의 문자열')=='침례 검증용 임의 문자열'
    assert apply_review_receipts(store,read_block(file,tmp_path/'none'))[
        '성경 본문']['text_review_pending'] is True


def _approve_request(url,day,revision,ident):
    request={'date':day,'service':'sunday','revision':revision,'file_id':ident,'reviewed':True,
             'acknowledged_unresolved':['성경 본문:bible_review'],
             'confirmed_manual_reviews':['성경 본문:bible_review']}
    with urlopen(Request(url+'/api/complete',data=json.dumps(request).encode('utf8'),
                         method='POST',headers={'Content-Type':'application/json'}),timeout=8) as r:
        return json.load(r)


@pytest.mark.parametrize('source_modified',[False,True])
def test_http_explicit_ppt_approval_records_only_matching_generated_source(
    tmp_path,monkeypatch,source_modified
):
    file=source_with_passages(tmp_path,{'요3:16':'검수된 것으로 가정할 테스트 문장'})
    monkeypatch.setenv('MEDIA_BIBLE_FILE',str(file))
    monkeypatch.setenv('MEDIA_BIBLE_SOURCES',str(tmp_path/'verified-but-empty'))
    store=WorkStore(tmp_path/'work.db')
    day='2026-10-18'
    ident='f'*32
    data={'fields':{'성경 본문':{'state':'VALUE','value':'요 3:16'}},
          'outputs':{'ppt':{'fileId':ident,'changed':False,'complete':False}}}
    revision=store.save(day,'sunday',0,data)['revision']
    directory=Path(store.path).with_suffix('.generated')
    directory.mkdir(exist_ok=True)
    (directory/(ident+'.pptx')).write_bytes(b'synthetic generated PPT artifact')
    original=read_block(file,tmp_path/'verified-but-empty')
    digests=units_for_manual_confirmation(original,['성경 본문:bible_review'])
    report={'date':day,'service':'sunday','format':'pptx',
            'fields':data['fields'],'unresolved':['성경 본문:bible_review'],
            'connections':{},'attachments':[],
            'typography_version':SUNDAY_TYPOGRAPHY_VERSION,
            'render_configuration':render_configuration(data),
            'bible_review_digests':{'성경 본문':digests}}
    (directory/(ident+'.json')).write_text(json.dumps(report,ensure_ascii=False))
    if source_modified:
        file.write_text(json.dumps({'요3:16':'조작되거나 수정된 시험 문장'},ensure_ascii=False),encoding='utf-8')
    server=make_server(store,0)
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        url=f'http://127.0.0.1:{server.server_port}'
        if source_modified:
            with pytest.raises(HTTPError) as rejected:
                _approve_request(url,day,revision,ident)
            assert rejected.value.code==409
            assert store.bible_review_receipts(list(digests))=={}
            assert store.get(day,'sunday')['data']['outputs']['ppt']['complete'] is False
        else:
            approved=_approve_request(url,day,revision,ident)
            assert approved['data']['outputs']['ppt']['complete'] is True
            assert store.bible_review_receipts(list(digests))==digests
            subsequent=apply_review_receipts(store,read_block(file,tmp_path/'verified-but-empty'))
            assert subsequent['성경 본문']['text_review_pending'] is False
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
