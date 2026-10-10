"""One-shot PDF/PPTX preview does not create a lasting media library."""
from io import BytesIO
from pathlib import Path
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from reportlab.pdfgen import canvas

from media_automation.web.application import Application
from media_automation.web.server import make_server
from media_automation.web import preview_once


def pdf_bytes() -> bytes:
    target = BytesIO()
    pdf = canvas.Canvas(target)
    pdf.drawString(20, 20, "preview")
    pdf.save()
    return target.getvalue()


def test_pdf_preview_returns_bytes_without_retained_copy(tmp_path):
    payload = pdf_bytes()
    before = list(tmp_path.rglob("*"))
    assert preview_once.preview_once("bulletin.pdf", payload) == payload
    assert list(tmp_path.rglob("*")) == before


def test_pptx_preview_cleans_temporary_directory(monkeypatch, tmp_path):
    payload = b"test-pptx-file"
    observed = []
    def fake_render(source: Path, output: Path):
        observed.append(source)
        assert source.read_bytes() == payload
        output.write_bytes(pdf_bytes())
    monkeypatch.setattr(preview_once, "convert_pptx", fake_render)
    result = preview_once.preview_once("service.pptx", payload)
    assert result.startswith(b"%PDF")
    assert not observed[0].exists()
    assert not (tmp_path / "uploads").exists()


def test_preview_rejects_other_formats_and_bad_pdf():
    for filename, content in (("archive.zip", b"data"),
                              ("../out.pdf", b"data"),
                              ("bad.pdf", b"bad"),
                              ("empty.pptx", b"")):
        with pytest.raises(ValueError):
            preview_once.preview_once(filename, content)


def test_http_preview_endpoint_requires_auth_and_writes_no_sessions(tmp_path):
    app = Application(tmp_path / "repo", tmp_path / "jobs")
    server, token = make_server(app, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_port}"
    payload = pdf_bytes()
    url = base + "/api/preview-once?filename=sample.pdf"
    try:
        with pytest.raises(HTTPError) as rejected:
            urlopen(Request(url, data=payload), timeout=4)
        assert rejected.value.code == 401
        with urlopen(Request(url, data=payload, headers={
            "Authorization": "Bearer " + token,
        }), timeout=4) as response:
            assert response.headers.get_content_type() == "application/pdf"
            assert response.read() == payload
        assert not app.existing.root.exists()
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_readiness_status_uses_three_explicit_states():
    source = (Path(__file__).parents[1] / "src/media_automation/web/static/app.js").read_text(encoding="utf-8")
    assert "UNSET" in source and "VALUE" in source and "NONE" in source
    assert "미제공" in source and "이번 주 없음" in source and "입력됨" in source
