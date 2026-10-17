"""Sunday bulletin defaults must use church settings, not a previous week's people."""
import json

import pytest

from media_automation.web.original import bulletin_generation as bulletin
from media_automation.web.original.work_store import WorkStore


@pytest.mark.parametrize(
    "current,expected",
    [
        ({}, "이은철 목사"),
        ({"주일 인도자": {"state": "UNSET", "value": ""}}, "이은철 목사"),
        ({"주일 인도자": {"state": "VALUE", "value": "초청 인도자"}}, "초청 인도자"),
        ({"주일 인도자": {"state": "NONE", "value": ""}}, None),
    ],
)
def test_leader_defaults_only_when_not_explicitly_set(current, expected):
    assert bulletin.default_sunday_leader(current, {"담임목사": "이은철"}) == expected


def test_default_does_not_invent_an_unknown_pastor():
    assert bulletin.default_sunday_leader({}, {"담임목사": ""}) is None


@pytest.mark.parametrize("leader,expected", [
    (None, "이은철 목사"),
    ("초청 목사", "초청 목사"),
    ("none", None),
])
def test_web_bulletin_writes_the_correct_leader_and_reports_provenance(
    tmp_path, monkeypatch, leader, expected
):
    store = WorkStore(tmp_path / "review.db")
    fields = {
        "확정 주보 호수": {"state": "VALUE", "value": "13-42"},
        "성경 본문": {"state": "VALUE", "value": "마 16:13~18"},
        "설교 제목": {"state": "VALUE", "value": "교회가 소중한 이유"},
    }
    if leader == "none":
        fields["주일 인도자"] = {"state": "NONE", "value": ""}
    elif leader:
        fields["주일 인도자"] = {"state": "VALUE", "value": leader}
    store.save("2026-10-18", "sunday", 0, {"fields": fields})
    seen = {}

    def fake_renderer(document, destination, **_):
        seen["document"] = document
        destination.write_bytes(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(bulletin, "render_original_bulletin", fake_renderer)
    result = bulletin.generate_bulletin(
        store, {"date": "2026-10-18", "service": "sunday", "revision": 1}
    )
    assert seen["document"].worship.leader == expected
    assert "주일 인도자" not in result["unresolved"]
    report = json.loads(
        (tmp_path / "review.generated" / (result["file_id"] + ".json")).read_text()
    )
    assert report["derived_defaults"]["설교자"] == "이은철 목사"
    assert seen["document"].worship.preacher == "이은철 목사"
    assert "설교자" not in result["unresolved"]
    if leader is None:
        assert report["derived_defaults"]["주일 인도자"] == "이은철 목사"
        assert "주일 인도자" not in report["effective_fields"]
    else:
        assert "주일 인도자" not in report["derived_defaults"]


@pytest.mark.parametrize(
    "current, expected",
    [
        ({}, "이은철 목사"),
        ({"설교자": {"state": "UNSET", "value": ""}}, "이은철 목사"),
        ({"설교자": {"state": "VALUE", "value": "초청 설교자 목사"}}, "초청 설교자 목사"),
        ({"설교자": {"state": "NONE", "value": ""}}, None),
    ],
)
def test_preacher_defaults_only_when_unset(current, expected):
    assert bulletin.default_sunday_preacher(current, {"담임목사": "이은철"}) == expected


@pytest.mark.parametrize(
    "preacher, expected",
    [(None, "이은철 목사"), ("초청 목사", "초청 목사"), ("none", None)],
)
def test_generated_pdf_preacher_default_override_and_explicit_none(
    tmp_path, monkeypatch, preacher, expected
):
    store = WorkStore(tmp_path / "review.db")
    fields = {}
    if preacher == "none":
        fields["설교자"] = {"state": "NONE", "value": ""}
    elif preacher:
        fields["설교자"] = {"state": "VALUE", "value": preacher}
    store.save("2026-10-18", "sunday", 0, {"fields": fields})
    seen = {}

    def fake_renderer(document, dst, **_):
        seen["preacher"] = document.worship.preacher
        dst.write_bytes(b"%PDF-1.4\n%%EOF\n")

    monkeypatch.setattr(bulletin, "render_original_bulletin", fake_renderer)
    result = bulletin.generate_bulletin(
        store, {"date": "2026-10-18", "service": "sunday", "revision": 1}
    )
    report = json.loads(
        (tmp_path / "review.generated" / (result["file_id"] + ".json")).read_text()
    )
    assert seen["preacher"] == expected
    assert "설교자" not in result["unresolved"]
    assert report["derived_defaults"].get("설교자") == (
        "이은철 목사" if preacher is None else None
    )
    assert "설교자" not in report["effective_fields"] if preacher is None else True
    assert store.get("2026-10-18", "sunday")["data"]["fields"] == fields


def test_missing_pastor_setting_does_not_invent_preacher():
    assert bulletin.default_sunday_preacher({}, {"담임목사": ""}) is None
