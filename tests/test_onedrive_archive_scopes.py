"""Archive browsing must use the configured worship folder, not only archive root.

Only GitHub-safe mocks. Actual OneDrive upload and playback require Mac checks.
"""
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from media_automation.web.original.onedrive_http import handle


@pytest.mark.parametrize('purpose', [
    'archive', 'archive_wednesday', 'archive_friday_zoom', 'archive_friday_in_person',
    'archive_sunday_ppt', 'archive_sunday_pdf',
])
def test_archive_viewer_scoped_folder_route(purpose):
    queried = []
    class Cloud:
        def list_selected(self, p, identifier, query):
            queried.append((p, identifier, query))
            return [{'id':'uploaded','name':'2026-10-16-friday.pptx','file':{}}]
    class Handler:
        command = 'GET'
        headers = {}
        replies = []
        def reply(self, status, body):
            self.replies.append((status, body))
    h=Handler()
    h.replies=[]
    path='/api/onedrive/files?purpose='+purpose
    assert handle(Cloud(), h, urlsplit(path), 'http://localhost:18877', True, 'test-session', True)
    assert queried==[(purpose,None,'')]
    assert h.replies[-1][0]==200
    assert h.replies[-1][1]['items'][0]['id']=='uploaded'


def test_archive_viewer_does_not_allow_unrelated_one_drive_purpose():
    class Cloud:
        def list_selected(self, purpose, identifier, query):
            raise AssertionError('Unauthorised purpose should be blocked')
    class Handler:
        command='GET'
        headers={}
        replies=[]
        def reply(self, status, body):
            self.replies.append((status,body))
    h=Handler()
    h.replies=[]
    assert handle(Cloud(),h,urlsplit('/api/onedrive/files?purpose=private'), 'http://localhost:18877',True,'s',True)
    assert h.replies[-1][0]==400


def test_archive_ui_uses_selected_folder_scopes():
    from pathlib import Path
    src=Path('src/media_automation/web/original/ui/onedrive.js').read_text()
    chunk=src[src.index('async function archives('):src.index('async function archiveCurrent(')]
    assert 'state?.folders?.[key]' in chunk
    assert "encodeURIComponent(chosen)" in chunk
    assert "archives(chosen,item.id)" in chunk
    assert "OneDrive에서 열기" in chunk
    # Only user-selected folders, not Graph global search.
    assert 'search(q=' not in chunk


def test_archive_retry_reports_failed_prerequisites():
    from pathlib import Path
    src=Path('src/media_automation/web/original/ui/onedrive.js').read_text()
    chunk=src[src.index('async function archiveCurrent('):src.index('async function syncOriginal(')]
    assert 'if(!(state.folders?.archive||state.folders?.[keyName]))throw Error' in chunk
    assert 'status.textContent' in chunk
    assert 'finally{button.disabled=false;}' in chunk
