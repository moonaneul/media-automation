"""Missing score originals can only be restored to an isolated review store."""
import hashlib
from pathlib import Path

import pytest

from media_automation.web.original.work_store import WorkStore
from scripts.restore_review_sources import recover


def store_with_missing_source(tmp_path, filename="1.ppt", content=b"original-score"):
    review = tmp_path / "media-automation-ui-review"
    source = tmp_path / "media-automation"
    source.mkdir()
    db = review / "output/ui-review/work.db"
    db.parent.mkdir(parents=True)
    store = WorkStore(db)
    asset = store.attach("2026-10-14", "wednesday", "시작 찬양 1", filename, content)
    digest = asset["digest"]
    recorded = db.with_suffix(".files") / digest
    recorded.unlink()  # simulate isolated DB without its blob; original elsewhere
    return review, source, db, digest, content


def test_dry_run_finds_digest_but_does_not_write_to_review(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path)
    original = source / "output/old/work.files" / digest
    original.parent.mkdir(parents=True)
    original.write_bytes(content)
    result = recover(db, review, [source], matches=["1.ppt"], restore=False)
    assert result == {"registered":1, "already_valid":0, "found":1, "copied":0, "missing":0}
    assert not (db.with_suffix(".files") / digest).exists()
    assert original.read_bytes() == content


def test_restore_only_exact_digest_and_leave_source_untouched(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path, filename="300장.ppt")
    original = source / "assets/private/300장.ppt"
    original.parent.mkdir(parents=True)
    original.write_bytes(content)
    stale = source / "output/backup/work.files" / digest
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"other content")
    result = recover(db, review, [source], matches=["300"], restore=True)
    recovered = db.with_suffix(".files") / digest
    assert result["copied"] == 1
    assert recovered.read_bytes() == content
    assert recovered.stat().st_ino != original.stat().st_ino  # no hardlink to originals
    assert stale.read_bytes() == b"other content"
    assert original.read_bytes() == content
    again = recover(db, review, [source], matches=["300"], restore=True)
    assert again["already_valid"] == 1 and again["copied"] == 0


def test_wrong_file_same_name_never_restored(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path)
    fake = source / "1.ppt"
    fake.write_bytes(b"different-but-same-name")
    result = recover(db, review, [source], matches=["1.ppt"], restore=True)
    assert result["missing"] == 1
    assert result["copied"] == 0
    assert not (db.with_suffix(".files") / digest).exists()


def test_restore_rejects_symlink_into_original(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path)
    real = source / "original"
    real.mkdir()
    (real / digest).write_bytes(content)
    files = db.with_suffix(".files")
    files.rmdir()
    files.symlink_to(real, target_is_directory=True)
    with pytest.raises(ValueError, match="심볼릭 링크"):
        recover(db, review, [source], restore=True)
    assert (real / digest).read_bytes() == content


def test_restore_rejects_db_outside_review_root(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path)
    with pytest.raises(ValueError, match="검수 DB"):
        recover(db, source, [review], restore=True)


def test_restore_by_original_name_for_filename_only_asset(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path, filename="300장_새찬송.ppt")
    original = source / "old-files/300장_새찬송.ppt"
    original.parent.mkdir()
    original.write_bytes(content)
    result = recover(db, review, [source], matches=["300"], restore=True)
    assert result["copied"] == 1


def test_existing_wrong_target_is_not_overwritten(tmp_path):
    review, source, db, digest, content = store_with_missing_source(tmp_path)
    path = db.with_suffix(".files") / digest
    path.write_bytes(b"corrupt")
    original = source / digest
    original.write_bytes(content)
    result = recover(db, review, [source], restore=True)
    assert result["copied"] == 0
    assert path.read_bytes() == b"corrupt"
