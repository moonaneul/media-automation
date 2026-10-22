"""Local/Windows/GitHub boundaries: synthetic Git checkouts, no real user DB."""
from importlib.util import module_from_spec, spec_from_file_location
import os
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/check_workspace_split.py"
spec = spec_from_file_location("workspace_split_audit", SCRIPT)
tool = module_from_spec(spec)
spec.loader.exec_module(tool)


def git(repo, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True, timeout=12,
    )
    return proc.stdout.strip()


@pytest.fixture
def checkout(tmp_path):
    repo = tmp_path / "review-checkout"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Synthetic Tester")
    git(repo, "config", "user.email", "fake@example.invalid")
    (repo / ".gitignore").write_text(
        "sources/\nsource/\ninput/\noutput/\noutputs/\n"
        "data/private/\nassets/private/\n.env\n.env.*\n",
        encoding="utf-8",
    )
    (repo / "wednesday.py").write_text("# synthetic command\n", encoding="utf-8")
    git(repo, "add", ".gitignore", "wednesday.py")
    git(repo, "commit", "-q", "-m", "synthetic baseline")
    return repo


def test_sensitive_guard_catches_hidden_dot_env_and_private_paths():
    for name in (
        ".env", "./.env", ".env.production", "./.env.local",
        "output/works.db", "sources/original.pptx", "input/weekly.yaml",
        "data/private/bible.json", "assets/private/original.png",
        "connection.pem", "work.sqlite3", "sensitive.key",
    ):
        assert tool._is_sensitive(name), name
    assert not tool._is_sensitive("docs/README.md")
    assert not tool._is_sensitive("src/media_automation/cloud/worker.py")


def test_clean_synthetic_checkout_reports_only_path_presence_not_db_bytes(checkout):
    work = checkout / "output"
    work.mkdir()
    db = work / "work.db"
    db.write_bytes(b"SENSITIVE TEST DATABASE CONTENT NEVER PRINT")
    (work / "main-database.txt").write_text("output/work.db", encoding="utf-8")
    (checkout / "input").mkdir()
    (checkout / "sources").mkdir()
    report = tool.collect(checkout, environ={})
    assert report["schema"] == "media-automation/workspace-split-v1"
    assert report["git"]["has_local_changes"] is False
    assert report["git"]["tracked_private_entries"] == 0
    assert report["database"] == {
        "source": "output/main-database.txt",
        "selected_database_exists": True,
        "selected_database_within_checkout": True,
        "selection_problem": None,
        "database_contents_inspected": False,
    }
    assert all(report["protected_directories_ignored"].values())
    assert report["local_directories_present"]["sources"] is True
    assert report["local_directories_present"]["weekly_inputs"] is True
    serialized = json.dumps(report, ensure_ascii=False)
    assert str(checkout) not in serialized
    assert db.name not in serialized
    assert "SENSITIVE TEST DATABASE CONTENT" not in serialized
    assert report["files_written_or_deleted"] is False
    assert db.read_bytes() == b"SENSITIVE TEST DATABASE CONTENT NEVER PRINT"


def test_missing_pointer_fails_closed_without_generating_empty_database(checkout):
    pointer = checkout / "output/main-database.txt"
    pointer.parent.mkdir()
    pointer.write_text("  ", encoding="utf-8")
    report = tool.collect(checkout, environ={})
    assert report["database"]["selection_problem"] == "pointer_missing_or_invalid"
    assert report["database"]["selected_database_exists"] is False
    assert not list(pointer.parent.glob("*.db"))


def test_uncommitted_file_name_and_environment_secret_never_enter_report(checkout):
    (checkout / "top-secret-worship-offering-notice.txt").write_text(
        "PRIVATE NAME FOR DEMONSTRATION", encoding="utf-8"
    )
    report = tool.collect(
        checkout,
        environ={"MEDIA_DATABASE": "secrets/never-publish-actual-db.db",
                 "ONEDRIVE_CLIENT_SECRET": "DO-NOT-PRINT-THIS"},
    )
    assert report["git"]["has_local_changes"] is True
    assert report["git"]["untracked_entries"] == 1
    assert report["code_review_before_pull_or_switch_required"] is True
    output = json.dumps(report, ensure_ascii=False)
    assert "top-secret-worship-offering" not in output
    assert "never-publish-actual-db" not in output
    assert "DO-NOT-PRINT-THIS" not in output


def test_existing_external_database_location_is_flagged_not_read_or_copied(checkout, tmp_path):
    external = tmp_path / "existing-outside-work.sqlite"
    external.write_bytes(b"EXTERNAL DB MUST NOT BE READ")
    report = tool.collect(checkout, environ={"MEDIA_DATABASE": str(external)})
    assert report["database"]["selected_database_exists"] is True
    assert report["database"]["selected_database_within_checkout"] is False
    assert "selected_local_database_outside_checkout_check_intended_path" in report["warnings"]
    assert external.read_bytes() == b"EXTERNAL DB MUST NOT BE READ"


def test_compare_code_versions_never_claims_weekly_data_equal(checkout, tmp_path):
    a = tool.collect(checkout, environ={})
    b = json.loads(json.dumps(a))
    b["git"]["head_sha"] = "1" * 40
    compare = tool.compare(a, b)
    assert compare["branches_match"] is True
    assert compare["code_commits_match"] is False
    assert compare["database_data_equality_verified"] is False
    assert compare["private_data_auto_sync_performed"] is False
    with pytest.raises(ValueError):
        tool.compare(a, {"schema": "not-our-report"})


def test_repo_guard_blocks_tracked_private_file_even_if_ignore_is_present(checkout):
    (checkout / ".env").write_text("TEST_SECRET_NOT_REAL=1", encoding="utf-8")
    git(checkout, "add", "--force", ".env")
    report = tool.collect(checkout, environ={})
    assert report["git"]["tracked_private_entries"] == 1
    assert "private_or_database_file_tracked_by_git" in report["warnings"]
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(checkout), "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 2
    assert "TEST_SECRET_NOT_REAL" not in result.stdout
    assert "TEST_SECRET_NOT_REAL" not in result.stderr


def test_script_read_only_check_passes_on_clean_synthetic_checkout(checkout):
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(checkout), "--check", "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["files_written_or_deleted"] is False
    assert report["git"]["tracked_private_entries"] == 0


@pytest.mark.parametrize("tracked_private", [False, True])
def test_workspace_check_prints_on_windows_cp949_stdout(checkout, tracked_private):
    """Windows redirected stdout must not crash on an unencodable em dash."""
    if tracked_private:
        (checkout / ".env").write_text("SYNTHETIC", encoding="utf-8")
        git(checkout, "add", "-f", ".env")
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "cp949"
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(checkout), "--check"],
        cwd=ROOT, capture_output=True, env=env, timeout=15, check=False,
    )
    assert result.returncode == (2 if tracked_private else 0), result.stderr
    assert b"WORKSPACE SPLIT - READ ONLY" in result.stdout
    assert b"UnicodeEncodeError" not in result.stderr
