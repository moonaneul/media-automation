"""Safety checks for repository restructuring; do not touch user's workspace."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_repository_layout.py"
spec = spec_from_file_location("read_only_repository_audit", SCRIPT)
audit = module_from_spec(spec)
spec.loader.exec_module(audit)


def test_historical_snapshots_are_not_treated_as_live_runtime():
    assert audit.classify("experiments/desktop-webapp-20261010/output/design/old.py") == "historical_reference"
    assert audit.classify("src/media_automation/_legacy_migration/backend/server.py") == "historical_reference"
    assert audit.classify("scripts/archive/validate_friday_zoom.py") == "historical_reference"
    assert audit.classify("src/media_automation/web/original/server.py") == "active_application"
    assert audit.classify("src/media_automation/cloud/worker.py") == "active_application"
    assert audit.classify("scripts/run_original_blue.py") == "maintenance_and_legacy_cli"
    assert audit.classify("wednesday.py") == "supported_entrypoints"


def test_input_sources_and_private_data_never_allowed_into_git():
    for path in [
        "sources/past-worship.pptx", "source/private.png",
        "output/main/work.db", "input/friday/personal.mp3",
        "assets/private/bulletin/original-design.pdf",
        "data/private/bible_fixed.json", ".env",
        ".env.cloud", "media.sqlite3", "private.key",
    ]:
        assert audit.forbidden_tracked(path), path
    for path in [
        "data/bulletin_number_anchor.yaml",
        "src/media_automation/weekly_cli.py",
        "experiments/desktop-webapp-20261010/output/example.py",
        "docs/repository_layout_20261022.md",
    ]:
        assert not audit.forbidden_tracked(path), path


def test_repo_check_is_read_only_and_supported_entrypoints_remain_available():
    report = audit.inventory()
    assert report["files_modified"] is False
    assert report["safe_to_delete_anything_automatically"] is False
    assert report["protected_tracked_paths"] == []
    assert report["missing_supported_entrypoints"] == []
    assert report["groups"]["active_application"] > 50
    assert report["groups"]["historical_reference"] > 10
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--check"],
        cwd=ROOT, text=True, capture_output=True, check=False, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_archived_copy_check_never_modifies_original(tmp_path):
    (tmp_path / "src/media_automation").mkdir(parents=True)
    (tmp_path / "experiments").mkdir()
    original = tmp_path / "src/media_automation/example.py"
    archived = tmp_path / "experiments/example.py"
    original.write_text("def preserved():\n    return 1\n", encoding="utf-8")
    archived.write_bytes(original.read_bytes())
    before = (original.read_bytes(), archived.read_bytes())
    duplicates = audit.exact_historical_copies(
        ["src/media_automation/example.py", "experiments/example.py"], tmp_path
    )
    assert duplicates == [{"historical": "experiments/example.py",
                           "active": "src/media_automation/example.py"}]
    assert before == (original.read_bytes(), archived.read_bytes())
