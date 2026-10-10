"""Regression tests for original HWP notice extraction route."""
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest

from media_automation.web.application import Application
from media_automation.web.server import make_server
from media_automation.web import notice_files


def test_hwp_notice_rejects_invalid_and_hwpx():
    with pytest.raises(ValueError):
        notice_files.extract_notice("../evil.hwp", b"x")
    with pytest.raises(ValueError, match="HWPX"):
        notice_files.extract_notice("notice.hwpx", b"x")


def test_hwp_notice_reads_using_canonical_parser(monkeypatch, tmp_path):
    class Result:
        returncode = 0
        stdout = "찬양1: 주님을 찬양\n기도: 홍길동\n"
    calls = []
    def fake_run(args, **kwargs):
        calls.append((args, kwargs))
        assert args[0]
        assert args[-1].endswith("notice.hwp")
        return Result()
    monkeypatch.setattr(notice_files.subprocess, "run", fake_run)
    text = notice_files.extract_notice("주보(10_11).hwp", b"binary-hwp-data")
    assert "찬양1" in text and "기도" in text
    assert len(calls) == 1


def test_hwp_notice_http_requires_token_and_uses_original_query(tmp_path, monkeypatch):
    monkeypatch.setattr("media_automation.web.server.extract_notice",
                        lambda filename, body: "제목: " + filename)
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("wednesday", "friday", "sunday", "bulletin"):
        (repo / f"{name}.py").write_text("pass\n", encoding="utf-8")
    server, token = make_server(Application(repo, tmp_path / "jobs"), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}/api/notice-file?filename=notice.hwp"
        with pytest.raises(HTTPError) as denied:
            urlopen(Request(base, data=b"hwp"))
        assert denied.value.code == 401
        with urlopen(Request(base, data=b"hwp", headers={"Authorization": "Bearer " + token})) as response:
            assert "notice.hwp" in response.read().decode("utf-8")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
