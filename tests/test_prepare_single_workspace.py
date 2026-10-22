"""Synthetic no-overwrite migration preflight; never touches real church files."""
from importlib.util import module_from_spec, spec_from_file_location
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/prepare_single_workspace.py"
spec = spec_from_file_location("safe_unified_data_staging", TOOL)
mod = module_from_spec(spec)
spec.loader.exec_module(mod)


@pytest.fixture
def checkouts(tmp_path):
    old, new = tmp_path / "legacy-folder", tmp_path / "review-folder"
    for folder in (old, new):
        folder.mkdir()
        subprocess.run(["git", "init", "-q", str(folder)],
                       check=True, capture_output=True)
    return old, new


def test_default_report_does_not_move_copy_or_read_db_contents(checkouts):
    old, new = checkouts
    (old / "input/wednesday").mkdir(parents=True)
    example = old / "input/wednesday/notice.txt"
    example.write_text("Synthetic weekly input, not real church data", encoding="utf-8")
    (old / "output").mkdir()
    original_db = old / "output/work.db"
    original_db.write_bytes(b"REAL USER DB MUST NEVER BE READ HERE")
    preview = mod.run(old, new)
    assert preview["mode"] == "DRY_RUN"
    assert preview["copy_candidates"] == 1
    assert preview["candidate_bytes"] == example.stat().st_size
    assert preview["old_files_deleted"] is False
    assert preview["existing_files_overwritten"] is False
    assert original_db.read_bytes() == b"REAL USER DB MUST NEVER BE READ HERE"
    assert not (new / "input").exists()


def test_explicit_copy_of_missing_source_is_verified_and_repeatable(checkouts):
    old, new = checkouts
    (old / "sources").mkdir()
    original = old / "sources/sample.txt"
    original.write_bytes(b"FAKE SOURCE DATA ONLY")
    first = mod.run(old, new, copy=True)
    assert first["copied"] == 1
    assert (new / "sources/sample.txt").read_bytes() == original.read_bytes()
    second = mod.run(old, new, copy=True)
    assert second["copied"] == 0
    assert second["identical_files"] == 1
    assert original.read_bytes() == b"FAKE SOURCE DATA ONLY"


def test_collision_never_overwrites_newer_weekly_input(checkouts):
    old, new = checkouts
    (old / "input").mkdir()
    (new / "input").mkdir()
    old_file = old / "input/data.yaml"
    new_file = new / "input/data.yaml"
    old_file.write_text("older", encoding="utf-8")
    new_file.write_text("newer", encoding="utf-8")
    with pytest.raises(ValueError, match="충돌"):
        mod.run(old, new, copy=True)
    assert new_file.read_text(encoding="utf-8") == "newer"
    assert old_file.read_text(encoding="utf-8") == "older"


def test_never_copy_credentials_database_and_connection_state(checkouts):
    old, new = checkouts
    (old / "input/work.onedrive").mkdir(parents=True)
    (old / "input/work.onedrive/token.txt").write_text("FAKE TOKEN", encoding="utf-8")
    (old / "input/work.db").write_bytes(b"FAKE DB")
    (old / "input/.env.production").write_text("FAKE SECRET", encoding="utf-8")
    (old / "input/normal.txt").write_text("OK", encoding="utf-8")
    report = mod.run(old, new, copy=True)
    assert report["copied"] == 1
    assert report["blocked_credentials_and_live_databases"] >= 2
    assert not (new / "input/work.db").exists()
    assert not (new / "input/work.onedrive").exists()
    assert not (new / "input/.env.production").exists()


def test_git_lfs_pointer_requires_human_attention_before_any_copy(checkouts):
    old, new = checkouts
    (old / "input").mkdir()
    (old / "input/sample.mp4").write_bytes(
        b"version https://git-lfs.github.com/spec/v1\n"
        b"oid sha256:" + b"a" * 64 + b"\nsize 9000\n"
    )
    report = mod.run(old, new)
    assert report["lfs_placeholders_skipped"] == 1
    with pytest.raises(ValueError, match="Git LFS"):
        mod.run(old, new, copy=True)
    assert not (new / "input").exists()


def test_generated_ppt_outputs_are_opt_in_and_live_sqlite_stays_out(checkouts):
    old, new = checkouts
    (old / "output").mkdir()
    (old / "output/approved.pdf").write_bytes(b"SYNTHETIC OUTPUT")
    (old / "output/work.db").write_bytes(b"SHOULD NOT TRANSFER ACTIVE SQLITE")
    assert mod.run(old, new)["copy_candidates"] == 0
    preview = mod.run(old, new, include_output=True)
    assert preview["copy_candidates"] == 1
    assert preview["blocked_credentials_and_live_databases"] == 1
    moved = mod.run(old, new, include_output=True, copy=True)
    assert moved["copied"] == 1
    assert not (new / "output/work.db").exists()


def test_symlink_not_followed_or_copied(checkouts, tmp_path):
    old, new = checkouts
    secret = tmp_path / "outside.txt"
    secret.write_text("EXTERNAL SYNTHETIC", encoding="utf-8")
    (old / "input").mkdir()
    link = old / "input/outside.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks unavailable")
    state = mod.run(old, new)
    assert state["symlinks_skipped"] == 1
    with pytest.raises(ValueError, match="링크"):
        mod.run(old, new, copy=True)
    assert not (new / "input").exists()


def test_checkouts_must_be_distinct_existing_git_roots(checkouts):
    old, new = checkouts
    with pytest.raises(ValueError, match="같거나"):
        mod.run(old, old)
    with pytest.raises(ValueError, match="존재"):
        mod.run(old, new / "not-yet-created")


def test_cli_defaults_to_no_write_report_and_redacts_path_names(checkouts):
    old, new = checkouts
    (old / "sources").mkdir()
    (old / "sources/secret-named-fixture.txt").write_text("SYNTHETIC", encoding="utf-8")
    output = subprocess.run(
        [sys.executable, str(TOOL), "--source", str(old), "--destination", str(new)],
        capture_output=True, text=True, check=False, timeout=15, cwd=ROOT
    )
    assert output.returncode == 0, output.stderr
    data = json.loads(output.stdout)
    assert data["copy_candidates"] == 1
    assert data["copied"] == 0
    assert "secret-named-fixture" not in output.stdout
    assert not (new / "sources").exists()
