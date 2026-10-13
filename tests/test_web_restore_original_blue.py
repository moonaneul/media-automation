"""Original UI fidelity and route tests. Do not alter production documents."""
import threading
from urllib.request import urlopen
from pathlib import Path
from media_automation.web.application import Application
from media_automation.web.server import make_server
from media_automation.web import blue_original


def test_original_blue_page_keeps_real_editable_workflow():
    source = (Path(blue_original.__file__).resolve().parent.parent /
              "_legacy_migration/ui/index.html").read_text(encoding="utf-8")
    page = blue_original.page().decode("utf-8")
    for ident in ("form-groups", "notice-dialog", "notice-text", "parse-notice",
                  "song-register-form", "service-title", "asset-list",
                  "friday-mode-box", "bulletin-settings-editor", "review-dialog",
                  "team-names"):
        if ident == "friday-mode-box":
            # This element is created at runtime by the exact original JS.
            assert ident in blue_original.resource("/blue-original.js")[0].decode("utf-8")
        else:
            assert f'id="{ident}"' in page
            assert f'id="{ident}"' in source
    assert 'src="/blue-original.js"' in page
    assert 'href="/blue-original.css"' in page
    assert "function form()" in blue_original.resource("/blue-original.js")[0].decode()
    assert "function parse()" in blue_original.resource("/blue-original.js")[0].decode()
    assert "function renderFridayMode()" in blue_original.resource("/blue-original.js")[0].decode()


def test_original_blue_route_does_not_replace_existing_site(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for service in ("sunday", "wednesday", "friday", "bulletin"):
        (repo / (service + ".py")).write_text("pass\n", encoding="utf-8")
    app = Application(repo, tmp_path / "jobs")
    server, token = make_server(app, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = "http://127.0.0.1:" + str(server.server_port)
        with urlopen(url) as response:
            root = response.read().decode()
        assert 'id="existing-upload"' in root
        with urlopen(url + "/blue-original") as response:
            restored = response.read().decode()
        assert 'id="form-groups"' in restored
        assert 'id="parse-notice"' in restored
        for path in ("/blue-original.css", "/blue-original.js",
                     "/blue-auth.js", "/bulletin-number.js",
                     "/notice-parser.js", "/song-search.js"):
            with urlopen(url + path) as response:
                assert response.status == 200
                assert response.read()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
