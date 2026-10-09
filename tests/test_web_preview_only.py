"""Preview-only UI and bounded disposable cache tests."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from media_automation.web import existing_inspections, job_previews


def test_preview_copy_expires_without_touching_original(tmp_path):
    source = tmp_path / "original.pptx"
    source.write_bytes(b"dummy-preview-copy")
    lib = existing_inspections.ExistingInspections(tmp_path / "jobs" / "_existing_inspections")
    item = lib.create("sunday", "2026-09-27", source.name, source.read_bytes())
    folder = lib._dir(item["inspection_id"])
    assert item["preview_only"] is True
    record_path = folder / "inspection.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["expires_at"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert lib.list() == []
    assert not folder.exists()
    assert source.read_bytes() == b"dummy-preview-copy"


def test_legacy_review_records_are_never_auto_deleted(tmp_path):
    lib = existing_inspections.ExistingInspections(tmp_path / "existing")
    file = tmp_path / "old.pptx"
    file.write_bytes(b"previous")
    item = lib.create("sunday", "2026-09-27", "old.pptx", file.read_bytes())
    folder = lib._dir(item["inspection_id"])
    record_path = folder / "inspection.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record.pop("preview_only")
    record.pop("expires_at")
    record_path.write_text(json.dumps(record), encoding="utf-8")
    lib._cleanup_preview_sessions()
    assert folder.exists()


def test_temporary_upload_usage_limit(monkeypatch, tmp_path):
    lib = existing_inspections.ExistingInspections(tmp_path / "cache")
    monkeypatch.setattr(existing_inspections, "PREVIEW_CAP_BYTES", 4)
    with pytest.raises(ValueError, match="512MiB"):
        lib.create("sunday", "2026-09-27", "song.pptx", b"12345")
    assert not lib.root.exists()


def test_generated_preview_cache_expires_not_pptx(tmp_path):
    source = tmp_path / "output" / "presentation.pptx"
    source.parent.mkdir()
    source.write_bytes(b"original-production-file")
    preview = job_previews._directory(tmp_path, "output/presentation.pptx")
    preview.mkdir(parents=True)
    cached = preview / "slides.pdf"
    cached.write_bytes(b"%PDF-fake-cached-preview")
    (preview / "metadata.json").write_text(json.dumps({
        "sha256": job_previews._sha256(source),
        "method": "powerpoint",
        "created_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
    }), encoding="utf-8")
    result = job_previews.status(tmp_path, "output/presentation.pptx", source)
    assert not result["available"]
    assert not cached.exists()
    assert source.read_bytes() == b"original-production-file"


def test_manual_review_fields_removed_from_web_markup():
    web = Path(__file__).parents[1] / "src/media_automation/web/static"
    html = (web / "index.html").read_text(encoding="utf-8")
    js = (web / "app.js").read_text(encoding="utf-8")
    assert "검수 기록 저장" not in html
    assert 'id="qa-human"' not in html
    assert 'id="existing-human"' not in html
    assert "preview-artifact" in html
    assert 'id="existing-file"' in html
    assert 'id="previous-jobs"' in html
    assert 'id="existing-list"' not in html
    assert 'id="existing-date"' not in html
    assert "qaCurrent" not in js
