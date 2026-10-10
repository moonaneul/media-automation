"""Full original-blue stack regression: UI + working APIs in one server.

Run with pytest; no church source files, actual database, or external ports
are modified. Production PPT/PDF generation is NOT asserted in this test.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "src/media_automation/_legacy_migration/backend"
sys.path.insert(0, str(BACKEND))

import server as legacy_server  # noqa: E402
from work_store import WorkStore  # noqa: E402


@pytest.fixture
def original_site(tmp_path):
    store = WorkStore(tmp_path / "work.sqlite")
    server = legacy_server.make_server(store, 0, None, "127.0.0.1")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        yield base, store
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=4)


def request(base, path, method="GET", data=None, content_type="application/json"):
    headers={}
    if data is not None:
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = content_type
    return urlopen(Request(base + path, data=data, headers=headers, method=method), timeout=3)


def test_original_blue_html_scripts_and_shared_mode(original_site):
    base, _ = original_site
    with request(base, "/") as res:
        html = res.read().decode("utf-8")
    assert "하늘빛기쁨 미디어 제작실" in html
    assert 'id="form-groups"' in html
    assert 'id="open-notice"' in html
    assert 'id="parse-notice"' in html
    assert 'id="song-register-form"' in html
    assert "function renderInputProgress()" in html
    for js in ("/bulletin-number.js", "/notice-parser.js", "/song-search.js"):
        with request(base, js) as res:
            assert res.status == 200 and res.read()
    with request(base, "/api/mode") as res:
        mode=json.load(res)
    assert mode["shared"] is True
    assert mode["local_only"] is True


def test_legacy_weekly_inputs_persist_and_conflicts_are_guarded(original_site):
    base, _ = original_site
    route="/api/work?service=sunday&date=2026-10-11"
    with request(base, route) as res:
        assert json.load(res)["revision"] == 0
    source={
        "fields":{
            "목장 본문":{"state":"VALUE", "value":"단 1:8~9"},
            "목장 제목":{"state":"VALUE", "value":"믿음과 상황이 충돌할 때"},
            "성경 본문":{"state":"UNSET", "value":""},
        },
        "source":"10/11\n<목장 말씀 나누기>",
        "sourceValues":{},
        "outputs":{"ppt":{"generated":False,"complete":False},
                   "pdf":{"generated":False,"complete":False}},
    }
    payload={"revision":0,"data":source}
    with request(base,route,"PUT",payload) as res:
        saved=json.load(res)
    assert saved["revision"] == 1
    with request(base,route) as res:
        latest=json.load(res)
    assert latest["data"]["fields"]["목장 본문"]["value"] == "단 1:8~9"
    assert latest["data"]["fields"]["성경 본문"]["state"] == "UNSET"
    with pytest.raises(HTTPError) as conflict:
        request(base,route,"PUT",payload)
    assert conflict.value.code == 409


def test_original_song_library_and_notice_upload_routes(original_site,monkeypatch):
    base, _ = original_site
    with request(base, "/api/songs") as res:
        assert json.load(res)["songs"] == []
    with request(base, "/api/songs", "POST", {
            "title":"시험 찬양","aliases":[],"edition":None,"number":None
        }) as res:
        assert res.status == 201
    with request(base, "/api/songs") as res:
        assert len(json.load(res)["songs"]) == 1
    monkeypatch.setattr(legacy_server,"extract_notice",
                        lambda filename, content: "찬양: 79, 337, 382장\n10/11")
    with request(base, "/api/notice-file?filename=notice.hwp", "POST",
                 b"HWP-BYTES", "application/octet-stream") as res:
        parsed=json.load(res)
    assert "79, 337" in parsed["text"]
    assert parsed["filename"] == "notice.hwp"
