"""Windows CP949-safe regression for the church web UI and its text reports.

This test uses a disposable localhost HTTP server and empty temporary DB,
without OneDrive credentials or actual worship files.
"""
import json
import threading
from pathlib import Path
from urllib.request import urlopen

from media_automation.web.original.server import make_server
from media_automation.web.original.work_store import WorkStore


ROOT = Path("src/media_automation/web/original")


def test_worship_web_root_serves_utf8_korean_html_with_no_codepage_dependency(tmp_path):
    server = make_server(WorkStore(tmp_path / "work.db"), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5) as response:
            assert response.status == 200
            assert response.headers.get_content_charset() == "utf-8"
            html = response.read().decode("utf-8")
        assert "수요예배" in html
        assert "주보" in html
        assert "__ENGINE_VERSION__" not in html
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_original_web_text_files_use_explicit_utf8_not_windows_ansi_default():
    """Regression for Windows default-CP949 source/report reads and writes."""
    for relative in (
        "server.py",
        "generation.py",
        "bulletin_generation.py",
        "ppt_preview.py",
        "bible_connection.py",
    ):
        contents = (ROOT / relative).read_text(encoding="utf-8")
        for line in contents.splitlines():
            if ".read_text(" in line or ".write_text(" in line:
                # The project runtime's HTML, YAML and JSON must not rely on
                # macOS/Linux UTF-8 as the implicit locale-specific default.
                assert "encoding=" in line, f"{relative}: {line.strip()}"
    assert "(UI / 'index.html').read_text(encoding='utf-8')" in (
        ROOT / "server.py"
    ).read_text(encoding="utf-8")
    assert ".write_text(json.dumps(report, ensure_ascii=False),encoding='utf-8')" in (
        ROOT / "generation.py"
    ).read_text(encoding="utf-8")
    assert ".write_text(json.dumps(report,ensure_ascii=False),encoding='utf-8')" in (
        ROOT / "bulletin_generation.py"
    ).read_text(encoding="utf-8")
