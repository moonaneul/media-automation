"""Sunday PPT archive uses the existing annual nested team folder; never creates one."""
from pathlib import Path

import pytest

from media_automation.web.original.onedrive import CloudError, OneDrive
from media_automation.web.original.work_store import WorkStore


@pytest.fixture
def cloud(tmp_path):
    store=WorkStore(tmp_path/'work.db')
    instance=OneDrive(store)
    with instance.lock:
        instance._write({'client_id':'mock','account':{'username':'mock@example.invalid'},
                         'folders':{'source':{'id':'source','name':'악보 PPT'}},
                         'shared_archives':{
                             'archive_sunday_ppt':{'id':'team_sunday','name':'01.주일예배',
                                                   'drive_id':'team_drive','redeemed':True},
                         }})
    return instance


def test_existing_nested_year_folder_is_target_with_zero_remote_writes(cloud,monkeypatch):
    scan=[]
    def children(folder_id, query='', *, drive_id=None):
        scan.append((folder_id,drive_id))
        if folder_id=='team_sunday':
            return [{'id':'ppts','name':'01.예배 PPT','folder':{}}]
        if folder_id=='ppts':
            return [{'id':'year_2025','name':'2025년','folder':{}},
                    {'id':'year_2026','name':'2026년','folder':{}}]
        raise AssertionError('Unexpected remote path '+str(folder_id))
    monkeypatch.setattr(cloud,'children',children)
    monkeypatch.setattr(cloud,'graph',lambda *args,**kwargs:pytest.fail('Must not create or alter folders'))
    root=cloud.archive_destination('sunday','ppt')
    assert root['id']=='team_sunday'
    folder=cloud.resolve_archive_output_folder(root,'2026-10-18','sunday','ppt')
    assert folder['id']=='year_2026'
    assert folder['drive_id']=='team_drive'
    assert scan==[('team_sunday','team_drive'),('ppts','team_drive')]
    assert cloud.selected('source')['id']=='source'
    assert cloud._read()['shared_archives']['archive_sunday_ppt']['id']=='team_sunday'


def test_annual_folder_is_selected_by_worship_date_not_current_time(cloud,monkeypatch):
    monkeypatch.setattr(cloud,'children',lambda parent,query='',*,drive_id=None:
        [{'id':'ppts','name':'01.예배 PPT','folder':{}}] if parent=='team_sunday'
        else [{'id':'y2026','name':'2026년','folder':{}},
              {'id':'y2027','name':'2027년','folder':{}}])
    root=cloud.archive_destination('sunday','ppt')
    assert cloud.resolve_archive_output_folder(root,'2026-12-27','sunday','ppt')['id']=='y2026'
    assert cloud.resolve_archive_output_folder(root,'2027-01-03','sunday','ppt')['id']=='y2027'


@pytest.mark.parametrize('absent', ['01.예배 PPT','2026년'])
def test_missing_nested_folder_blocks_incorrect_upload_and_does_not_create(
    cloud,monkeypatch,absent
):
    writes=[]
    def children(parent,query='',*,drive_id=None):
        if parent=='team_sunday':
            return [] if absent=='01.예배 PPT' else [{'id':'ppts','name':'01.예배 PPT','folder':{}}]
        if parent=='ppts':
            return [] if absent=='2026년' else [{'id':'year','name':'2026년','folder':{}}]
        raise AssertionError(parent)
    monkeypatch.setattr(cloud,'children',children)
    monkeypatch.setattr(cloud,'graph',lambda *args,**kwargs:writes.append(args) or None)
    with pytest.raises(CloudError,match='새 폴더는 자동 생성하지 않습니다'):
        cloud.resolve_archive_output_folder(
            cloud.archive_destination('sunday','ppt'),'2026-10-18','sunday','ppt')
    assert writes==[]


def test_no_change_to_bulletin_location(cloud):
    root={'id':'bulletin','drive_id':'team_drive','name':'00.주보','folder':{}}
    assert cloud.resolve_archive_output_folder(root,'2026-10-18','sunday','pdf')==root


def test_ui_explains_parent_share_link_and_date_based_year():
    html=Path('src/media_automation/web/original/ui/index.html').read_text('utf8')
    script=Path('src/media_automation/web/original/ui/onedrive.js').read_text('utf8')
    assert '바깥쪽 ‘01.주일예배’ 폴더의 공유 링크' in html
    assert '01.예배 PPT → 예배 날짜의 연도' in html
    assert "new URLSearchParams({service:svc,kind,mode,date})" in script
