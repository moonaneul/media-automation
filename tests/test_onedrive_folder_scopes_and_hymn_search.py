"""Worship source folders and per-service completion destinations are isolated.

All OneDrive calls are faked; no real Microsoft credentials or uploads needed.
"""
import pytest

from media_automation.web.original.onedrive import OneDrive, CloudError
from media_automation.web.original.work_store import WorkStore


def cloud(tmp_path, monkeypatch):
    drive = OneDrive(WorkStore(tmp_path / "review.db"))
    monkeypatch.setattr(drive, "selected", lambda purpose: {"id": "zoom" if purpose == "source_video" else "scores", "name": purpose})
    return drive


@pytest.mark.parametrize("file,query,expected", [
    ("380장_나의_힘이_되신_여호와.ppt", "380장", True),
    ("380 장 - 나의 힘이 되신 여호와.pptx", "380장", True),
    ("380_악보 PPT.ppt", "380장", True),
    ("새찬송가 380장.pptx", "380", True),
    ("새찬송가 380장.pptx", "380장", True),
    ("새찬송가 380장.pptx", "38장", False),
    ("새찬송가 138장.pptx", "380장", False),
    ("내 맘이.pptx", "내 맘이", True),
])
def test_match_korean_filename_unicode_and_hymn_number(file, query, expected):
    assert OneDrive._source_match(file, query) is expected


def test_missing_graph_index_search_falls_back_to_chosen_folder_and_nested_folders(tmp_path, monkeypatch):
    drive = cloud(tmp_path, monkeypatch)
    called = []
    files = {
        "scores": [{"id": "sub", "name": "하위 폴더", "folder": {}},
                   {"id": "other", "name": "제목 다른 곡.pptx", "file": {}}],
        "sub": [{"id": "song", "name": "380 장.pptx", "file": {}}],
    }
    def children(folder, query=""):
        called.append((folder,query))
        if query: return []
        return files.get(folder, [])
    monkeypatch.setattr(drive, "children", children)
    results = drive.list_selected("source", query="380장")
    assert [item["id"] for item in results] == ["song"]
    assert ("scores", "380장") in called
    assert ("sub", "") in called
    assert all(folder in ("scores", "sub") for folder, _ in called)


def test_graph_search_folder_only_result_does_not_suppress_fallback(tmp_path, monkeypatch):
    drive = cloud(tmp_path, monkeypatch)
    def children(folder, query=""):
        return [{"id": "sub", "name": "search suggestion", "folder": {}}] if query else [
            {"id": "match", "name": "새찬송가_380장.ppt", "file": {}}
        ]
    monkeypatch.setattr(drive, "children", children)
    assert drive.list_selected("source", query="380장")[0]["id"] == "match"


def test_video_folder_and_score_folder_are_different_search_roots(tmp_path, monkeypatch):
    drive=cloud(tmp_path, monkeypatch)
    calls=[]
    def children(folder, query=""):
        calls.append(folder)
        if query: return []
        return [{"id":"video", "name":"내찬양.mp4","file":{}}] if folder=="zoom" else []
    monkeypatch.setattr(drive,"children",children)
    assert drive.list_selected("source_video",query="내찬양")[0]["name"] == "내찬양.mp4"
    assert "scores" not in calls


def test_missing_explicit_archive_folder_uses_existing_root_hierarchy(tmp_path, monkeypatch):
    drive = OneDrive(WorkStore(tmp_path / "work.db"))
    monkeypatch.setattr(drive, "_read", lambda: {"folders": {"archive": {"id": "root-id", "name": "예배 완료본"}}})
    made=[]
    monkeypatch.setattr(drive,"children",lambda identifier: [])
    monkeypatch.setattr(drive,"graph", lambda route, **kwargs: (
        made.append(kwargs["body"]["name"]) or
        {"id":"made-"+str(len(made)), "name":kwargs["body"]["name"],"folder":{}}))
    dest=drive.archive_destination("sunday","pdf")
    assert dest["name"] == "주보"
    assert made == ["주일 예배","주보"]


@pytest.mark.parametrize("service,kind,mode,purpose", [
    ("wednesday","ppt",None,"archive_wednesday"),
    ("friday","ppt","zoom","archive_friday_zoom"),
    ("friday","ppt","in_person","archive_friday_in_person"),
    ("sunday","ppt",None,"archive_sunday_ppt"),
    ("sunday","pdf",None,"archive_sunday_pdf"),
])
def test_explicit_archive_destination_never_creates_or_replaces_hierarchy(tmp_path, monkeypatch,service,kind,mode,purpose):
    drive=OneDrive(WorkStore(tmp_path / "work.db"))
    assigned={purpose:{"id":"existing-"+purpose,"name":"교회 기존 위치","folder":{}}}
    monkeypatch.setattr(drive,"_read",lambda:{"folders":assigned})
    monkeypatch.setattr(drive,"children",lambda identifier: (_ for _ in ()).throw(AssertionError("should not create folders")))
    result=drive.archive_destination(service,kind,mode)
    assert result["id"]=="existing-"+purpose


def test_new_source_video_folder_is_not_allowed_to_overlap_score_folder(tmp_path, monkeypatch):
    drive=OneDrive(WorkStore(tmp_path / "work.db"))
    stored={"folders":{"source":{"id":"scores","name":"악보 PPT","folder":{}}}}
    monkeypatch.setattr(drive,"_read", lambda: stored)
    monkeypatch.setattr(drive,"_write",lambda value: stored.update(value))
    monkeypatch.setattr(drive,"item",lambda key:{
        "id":key, "name":key, "folder":{}, "parentReference":{"id":"scores","driveId":"one"}
    })
    monkeypatch.setattr(drive,"within", lambda item,folder: item["id"]==folder["id"])
    with pytest.raises(CloudError, match="겹치지"):
        drive.select_folder("source_video","scores")
