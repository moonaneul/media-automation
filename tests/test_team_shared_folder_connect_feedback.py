"""A failed team folder link must not be mistaken for a valid upload destination.

No OneDrive credentials or remote writes; this is the local HTTP API and UI
contract for the user's existing four church media team folders.
"""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore


def test_team_only_archive_rejects_unconnected_shared_folder_without_own_drive_write(tmp_path):
    store=WorkStore(tmp_path/"review.db")
    server=make_server(store,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    url=f"http://127.0.0.1:{server.server_port}/api/onedrive/archive"
    data={"date":"2026-10-18","service":"sunday","kind":"pdf","require_team_shared":True}
    try:
        req=Request(url,data=json.dumps(data).encode(),headers={"Content-Type":"application/json"},method="POST")
        try:
            urlopen(req,timeout=4)
            assert False,"Team-only archive must reject missing shared folder"
        except HTTPError as exc:
            error=json.load(exc)
            assert exc.code==400
            assert "00.주보" in error["error"]
            assert "개인 OneDrive로 대신 저장하지 않습니다" in error["error"]
        assert not Path(store.path).with_suffix(".generated").exists()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)


def test_shared_folder_link_failure_is_inline_not_only_a_temporary_toast():
    script=Path("src/media_automation/web/original/ui/onedrive.js").read_text()
    for role in ("archive_sunday_pdf","archive_sunday_ppt","archive_wednesday","archive_friday"):
        assert role in script
    assert "indicator.textContent='미연결 · '+folderName+' 연결 실패:" in script
    assert "indicator.textContent='연결 확인 중" in script
    assert "indicator.textContent='연결 성공 ·" in script
    assert "if(!state.shared_archives?.[role])requireBeforeUpload" in script
    assert "require_team_shared:true" in script
