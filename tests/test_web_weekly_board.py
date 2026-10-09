"""Week dashboard uses existing job metadata, never copies old inputs."""
from datetime import date, timedelta
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json

import pytest

from media_automation.web.weekly_board import build_dashboard
from media_automation.web.application import Application
from media_automation.web.server import make_server


def job(service, day, state, stamp, tag, artifacts=None):
    return {
        "service": service, "date": day, "state": state, "job_id": tag,
        "created_at": stamp, "artifacts": artifacts or [],
    }


def test_current_week_groups_wednesday_friday_sunday_and_bulletin():
    rows = [
        job("wednesday", "2026-10-07", "generated", "2026-10-05T00:00:00Z", "w1", ["done.pptx"]),
        job("friday", "2026-10-09", "needs_input", "2026-10-08T00:00:00Z", "f1"),
        job("sunday", "2026-10-11", "generated", "2026-10-06T00:00:00Z", "s1", ["done.pptx"]),
        job("bulletin", "2026-10-11", "failed", "2026-10-08T00:00:00Z", "b1"),
        job("wednesday", "2026-09-30", "generated", "2026-09-29T00:00:00Z", "older", ["done.pptx"]),
        job("wednesday", "2026-10-08", "generated", "2026-10-08T00:00:00Z", "wrong-date", ["done.pptx"]),
    ]
    result = build_dashboard(rows, "2026-10-09")
    assert (result["week_start"], result["week_end"]) == ("2026-10-05", "2026-10-11")
    by_type = {slot["service"]: slot for slot in result["slots"]}
    assert [x["service"] for x in result["slots"]] == ["wednesday", "friday", "sunday", "bulletin"]
    assert by_type["wednesday"]["latest"]["job_id"] == "w1"
    assert by_type["wednesday"]["latest"]["has_artifact"]
    assert len(by_type["wednesday"]["jobs"]) == 1
    assert by_type["friday"]["status"] == "자료 준비 중"
    assert by_type["sunday"]["date"] == by_type["bulletin"]["date"] == "2026-10-11"
    assert by_type["bulletin"]["status"] == "제작 실패"


def test_same_week_revisions_remain_distinct_and_not_auto_approved():
    old = job("wednesday", "2026-10-07", "generated", "2026-10-05T00:00:00Z", "old", ["one.pptx"])
    new = job("wednesday", "2026-10-07", "needs_input", "2026-10-06T00:00:00Z", "new")
    data = build_dashboard([old, new], "2026-10-07")["slots"][0]
    assert data["has_multiple"] is True
    assert [x["job_id"] for x in data["jobs"]] == ["new", "old"]
    assert data["status"] == "자료 준비 중"
    assert not data["latest"]["has_artifact"]
    assert data["jobs"][1]["has_artifact"] is True
    assert data["latest_generated"]["job_id"] == "old"


def test_empty_week_has_no_invented_work_and_year_boundary():
    result = build_dashboard([], "2027-01-01")
    assert result["week_start"] == "2026-12-28"
    assert result["week_end"] == "2027-01-03"
    assert all(x["latest"] is None and x["status"] == "아직 작업 없음" for x in result["slots"])
    with pytest.raises(ValueError):
        build_dashboard([], "not-a-date")


def test_weekly_endpoint_requires_auth_and_has_no_side_effects(tmp_path):
    app = Application(tmp_path / "repo", tmp_path / "jobs")
    server, token = make_server(app, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/weekly-board?date=2026-10-09"
    try:
        with pytest.raises(HTTPError) as denied:
            urlopen(endpoint, timeout=4)
        assert denied.value.code == 401
        request = Request(endpoint, headers={"Authorization": "Bearer " + token})
        with urlopen(request, timeout=4) as response:
            result = json.loads(response.read())
        assert result["week_start"] == "2026-10-05"
        assert len(result["slots"]) == 4
        assert not (tmp_path / "jobs").exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()
