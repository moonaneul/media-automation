from pathlib import Path
import pytest
from media_automation.web.original.work_store import WorkStore


def test_remove_attachment_preserves_other_service_and_library(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    song=store.register_song({'title':'테스트','aliases':[]})
    first=store.attach('2026-10-11','sunday','찬양 1','song.mp3',b'original',song['id'])
    store.attach('2026-10-14','wednesday','찬양 1','song.mp3',b'original')
    store.remove_original({'date':'2026-10-11','service':'sunday','slot':'찬양 1','digest':first['digest']})
    assert not store.attachments('2026-10-11','sunday')
    assert store.attachments('2026-10-14','wednesday')
    assert store.songs()[0]['assets']


def test_replace_and_delete_library_preserve_attachment_and_reset_review(tmp_path):
    store=WorkStore(tmp_path/'work.db');song=store.register_song({'title':'테스트','aliases':[]})
    old=store.attach('2026-10-11','sunday','찬양 1','old.mp3',b'old',song['id'])
    store.review_asset(song['id'],old['digest'],{'technical':True,'church':True,'permission':'allowed'})
    new=store.attach_song_asset(song['id'],'new.mp3',b'new',old['digest'])
    assets=store.songs()[0]['assets']
    assert len(assets)==1 and assets[0]['digest']==new['digest'] and not assets[0]['eligible']
    assert store.attachments('2026-10-11','sunday')[0]['digest']==old['digest']
    with pytest.raises(ValueError):store.attach_song_asset(song['id'],'oops.mp3',b'oops',old['digest'])
    assert store.songs()[0]['assets'][0]['digest']==new['digest']
    store.remove_original({'song_id':song['id'],'digest':new['digest']})
    assert not store.songs()[0]['assets']
    assert store.original(old['digest'])[0].read_bytes()==b'old'


def test_stale_attachment_delete_cannot_remove_replacement(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    old=store.attach('2026-10-11','sunday','찬양 1','old.mp3',b'old')
    new=store.attach('2026-10-11','sunday','찬양 1','new.mp3',b'new')
    store.remove_original({'date':'2026-10-11','service':'sunday','slot':'찬양 1','digest':old['digest']})
    assert store.attachments('2026-10-11','sunday')[0]['digest']==new['digest']
