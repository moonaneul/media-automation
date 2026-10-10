"""Blue integration route smoke test: original UI and job API must remain untouched."""
import threading
from urllib.request import urlopen
from urllib.error import HTTPError
from pathlib import Path
from media_automation.web.application import Application
from media_automation.web.server import make_server


def test_blue_route_is_separate_and_existing_route_unchanged(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("wednesday", "friday", "sunday", "bulletin"):
        (repo / f"{name}.py").write_text("print('test')\n", encoding="utf-8")
    app = Application(repo, tmp_path / "jobs")
    server, _token = make_server(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urlopen(base + "/") as response:
            original = response.read().decode("utf-8")
            assert "교회 미디어 제작실" in original
            assert 'id="existing-upload"' in original
        with urlopen(base + "/blue") as response:
            blue = response.read().decode("utf-8")
            assert "하늘빛기쁨 미디어 제작실" in blue
            assert 'id="job-list"' in blue
            assert 'id="qa-form"' in blue
            assert 'href="/blue.css"' in blue
        for path in ("/blue.js", "/blue.css"):
            with urlopen(base + path) as response:
                assert response.status == 200
                assert response.read()
        try:
            urlopen(base + "/api/jobs")
            assert False, "API incorrectly accessible without auth"
        except HTTPError as exc:
            assert exc.code == 401
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
