"""Real local HTTP round trip for Sunday bulletin review and cloud archiving.

The PDF renderer and OneDrive transport are stubbed; no church files, Microsoft
credentials, remote changes, or real worship approval is involved.
"""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from media_automation.web.original.work_store import WorkStore
from media_automation.web.original.server import make_server
from media_automation.web.original import bulletin_generation as bulletin
from media_automation.web.original import onedrive as onedrive_module


def field(value):
    return {"state": "VALUE", "value": value}


def absent():
    return {"state": "NONE", "value": ""}


def post(base, path, payload):
    request = Request(
        base + path,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.loads(exc.read())


def test_bulletin_review_http_completes_then_archives_without_touching_ppt(
    tmp_path, monkeypatch
):
    store = WorkStore(tmp_path / "review.db")
    day = "2026-10-18"
    # All known current-week required roles/verses are explicit. Optional
    # absence is declared NONE; no previous-week information is inherited.
    required = [
        "1부 찬양 인도자", "2부 찬양 인도자", "폐회 기도 담당자",
        "별도 찬송", "봉헌 찬송", "결단 찬송",
        "이번 주 1부 기도", "2부 기도 담당자",
        "이번 주 1부 봉헌기도", "2부 봉헌기도 담당자",
        "이번 주 설거지", "이번 주 수요예배 기도",
        "다음 주 1부 기도", "다음 주 2부 기도",
        "다음 주 1부 봉헌기도", "다음 주 2부 봉헌기도",
        "다음 주 설거지", "다음 주 수요예배 기도",
    ]
    fields = {name: absent() for name in required}
    fields.update({
        "확정 주보 호수": field("13-42"),
        "성경 본문": field("마 16:13~18"),
        "설교 제목": field("교회가 소중한 이유"),
        # 주일 인도자와 설교자는 둘 다 교회 기본 설정의 담임목사.
        # 추가 필드를 저장하지 않아도 완결된 주보가 생성되어야 한다.
        **{f"질문 {i}": field(f"확인된 질문 {i}") for i in range(1, 5)},
    })
    work = {"fields": fields, "outputs": {"ppt": {}, "pdf": {}}}
    revision = store.save(day, "sunday", 0, work)["revision"]

    # The church setting has to be confirmed before bulletin approval.
    settings = json.loads(
        Path(bulletin.__file__).with_name("bulletin-base-reference.json").read_text()
    )
    settings["status"] = "confirmed"
    with store.connect() as db:
        db.execute("CREATE TABLE bulletin_settings (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)")
        db.execute("INSERT INTO bulletin_settings VALUES (1,1,?)", (json.dumps(settings,ensure_ascii=False),))

    def render(_doc, path, **_kw):
        path.write_bytes(b"%PDF-1.4\nlocal synthetic bulletin only\n%%EOF\n")

    monkeypatch.setattr(bulletin, "render_original_bulletin", render)

    uploads = {}
    monkeypatch.setattr(
        onedrive_module.OneDrive,
        "archive_destination",
        lambda self, service, kind, mode=None: {"id": "synthetic-bulletin-folder"},
    )
    def upload(self, folder_id, name, content):
        assert folder_id == "synthetic-bulletin-folder"
        assert name.startswith("2026-10-18_sunday_pdf_")
        assert content.startswith(b"%PDF")
        uploads[name] = content
        return {"id": "synthetic-item-id", "name": name, "size": len(content), "file": {}}
    monkeypatch.setattr(onedrive_module.OneDrive, "upload_file", upload)

    server = make_server(store, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        # Produce from same date and revision via the actual local HTTP route.
        status, generated = post(base, "/api/build", {
            "date": day, "service": "sunday", "output": "pdf",
            "revision": revision, "groups": [],
        })
        assert status == 200, generated
        assert generated["unresolved"] == []
        pdf_id = generated["file_id"]
        report=json.loads(
            (Path(store.path).with_suffix(".generated")/(pdf_id+".json")).read_text()
        )
        assert report["derived_defaults"] == {
            "주일 인도자": "이은철 목사", "설교자": "이은철 목사"
        }
        work = store.get(day, "sunday")["data"]
        work["outputs"]["pdf"] = {
            "fileId": pdf_id, "generated": True,
            "complete": False, "changed": False, "unresolved": [],
        }
        revision = store.save(day, "sunday", revision, work)["revision"]

        # Clicking OneDrive before review must not bypass approval.
        status, rejected = post(base, "/api/onedrive/archive", {
            "date": day, "service": "sunday", "kind": "pdf",
        })
        assert status == 400, rejected
        assert not uploads

        status, reviewed = post(base, "/api/complete-bulletin", {
            "date": day, "service": "sunday", "revision": revision,
            "file_id": pdf_id, "reviewed": True,
        })
        assert status == 200, reviewed
        assert reviewed["data"]["outputs"]["pdf"]["complete"] is True
        assert reviewed["data"]["outputs"]["pdf"]["archiveStatus"] == "pending_connection"
        saved = store.get(day, "sunday")["data"]
        assert saved["outputs"]["pdf"]["complete"] is True
        assert saved["outputs"]["ppt"] == {}

        status, archived = post(base, "/api/onedrive/archive", {
            "date": day, "service": "sunday", "kind": "pdf",
        })
        assert status == 201, archived
        assert len(uploads) == 1
        assert archived["item"]["id"] == "synthetic-item-id"
        assert archived["work"]["data"]["outputs"]["pdf"]["archiveStatus"] == "uploaded"
        assert store.get(day, "sunday")["data"]["outputs"]["pdf"]["archiveStatus"] == "uploaded"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_bulletin_review_uses_church_preacher_without_extra_weekly_input(tmp_path, monkeypatch):
    store=WorkStore(tmp_path / "review.db")
    data={"fields":{"성경 본문":field("마 16:13~18"),"설교 제목":field("교회가 소중한 이유")}}
    revision=store.save("2026-10-18","sunday",0,data)["revision"]
    monkeypatch.setattr(
        bulletin, "render_original_bulletin",
        lambda _doc, path, **_: path.write_bytes(b"%PDF-1.4\n%%EOF\n")
    )
    result=bulletin.generate_bulletin(
        store,{"date":"2026-10-18","service":"sunday","revision":revision}
    )
    assert "설교자" not in result["unresolved"]
    assert result["complete"] is False



def test_pdf_review_returns_specific_missing_preacher_reason_and_never_marks_complete(
    tmp_path
):
    from media_automation.bulletin.original_design import LAYOUT_VERSION
    store=WorkStore(tmp_path/"review.db")
    date="2026-10-18"
    pdf_id="a" * 32
    fields={"설교자":{"state":"UNSET","value":""}}
    record={"fields":fields,"outputs":{"ppt":{},"pdf":{
        "fileId":pdf_id,"generated":True,"complete":False,"changed":False
    }}}
    revision=store.save(date,"sunday",0,record)["revision"]
    generated=tmp_path/"review.generated"
    generated.mkdir()
    (generated/(pdf_id+".pdf")).write_bytes(b"%PDF-1.4\n%%EOF")
    settings=json.loads(
        Path(bulletin.__file__).with_name("bulletin-base-reference.json").read_text()
    )
    (generated/(pdf_id+".json")).write_text(json.dumps({
        "layout_version":LAYOUT_VERSION,"format":"pdf","date":date,
        "service":"sunday","fields":fields,"unresolved":["설교자"],
        "settings":settings,
    },ensure_ascii=False))

    server=make_server(store,0)
    thread=threading.Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:
        status,response=post(f"http://127.0.0.1:{server.server_port}",
            "/api/complete-bulletin",{
                "date":date,"service":"sunday","file_id":pdf_id,
                "revision":revision,"reviewed":True
            })
        assert status == 409
        assert "설교자" in response["error"]
        assert "PDF를 다시 제작" in response["error"]
        output=store.get(date,"sunday")["data"]["outputs"]["pdf"]
        assert not output["complete"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
