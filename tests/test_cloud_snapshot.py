from copy import deepcopy
import hashlib
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

from media_automation.cloud.snapshot import SnapshotStore, materialize, validate_runtime_path


def sample():
    return {'day':'2026-10-14','service':'wednesday','work':{'revision':3,
        'data':{'fields':{'기도':{'state':'NONE','value':''}}},'updated_at':'2026-10-14T00:00:00Z'},
        'tables':{'files':[],'songs':[],'song_assets':[],'reviews':[],'attachments':[],
                  'settings':[{'id':1,'revision':1,'payload':{'status':'confirmed'}}],'runtime_assets':[]}}


def original(snapshot, data=b'original'):
    digest=hashlib.sha256(data).hexdigest()
    snapshot['tables']['files'].append({'digest':digest,'size':len(data),'drive_id':'drive','item_id':'item'})
    return digest


def cloud(data=b'original'):
    fake=Mock();fake.item.return_value={'id':'item','file':{},'size':len(data),'parentReference':{'driveId':'drive'}}
    fake.within.return_value=True;fake._download.return_value=data
    return fake


def test_snapshot_keeps_version_and_none_without_modifying_input(tmp_path):
    snap=sample();before=deepcopy(snap)
    store=SnapshotStore(tmp_path/'work.db',snap,cloud())
    assert store.get(snap['day'],snap['service'])['revision']==3
    assert store.get(snap['day'],snap['service'])['data']['fields']['기도']=={'state':'NONE','value':''}
    assert snap==before


def test_original_download_is_lazy_verified_and_cached(tmp_path):
    snap=sample();digest=original(snap);fake=cloud()
    store=SnapshotStore(tmp_path/'work.db',snap,fake)
    fake._download.assert_not_called()
    assert store.ensure_original(digest).read_bytes()==b'original'
    store.ensure_original(digest)
    assert fake._download.call_count==1


def test_wrong_original_hash_does_not_enter_cache(tmp_path):
    snap=sample();digest=original(snap);fake=cloud();fake._download.return_value=b'wrong'
    store=SnapshotStore(tmp_path/'work.db',snap,fake)
    with pytest.raises(ValueError):store.ensure_original(digest)
    assert not Path(store.path).with_suffix('.files').joinpath(digest).exists()


@pytest.mark.parametrize('path',['../secret','/tmp/file','assets/worship/../../file','data/private/other.json',
                                  'assets\\worship\\file','assets/worship//file'])
def test_runtime_path_cannot_escape_allowed_source_roots(path):
    with pytest.raises(ValueError):validate_runtime_path(path)


def test_bulletin_temp_store_and_environment_are_cleaned(monkeypatch):
    snap=sample();snap['service']='sunday';digest=original(snap)
    snap['tables']['runtime_assets']=[{'path':'assets/private/bulletin/'+n,'digest':digest} for n in ('original-design.pdf','original-regular.ttf','original-bold.ttf')]
    monkeypatch.setenv('MEDIA_BIBLE_FILE','original-value')
    with materialize(snap,cloud(),'pdf') as store:
        path=Path(store.path);assert path.exists()
        assert os.environ['MEDIA_BIBLE_FILE']!='original-value'
    assert not path.exists()
    assert os.environ['MEDIA_BIBLE_FILE']=='original-value'


def test_missing_design_is_rejected_before_blank_template_fallback():
    with pytest.raises(ValueError,match='design/Bible'):
        with materialize(sample(),cloud(),'ppt'):pass


def test_bulletin_missing_originals_fails_before_rendering():
    snap=sample();snap['service']='sunday'
    with pytest.raises(ValueError,match='bulletin design/fonts'):
        with materialize(snap,cloud(),'pdf'):pass
