"""Read-only script inventory checks: static reference != safe to delete."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/audit_script_usage.py"
spec = spec_from_file_location("script_catalog_audit", TOOL)
catalog = module_from_spec(spec)
spec.loader.exec_module(catalog)


def test_root_entrypoints_keep_executable_script_links():
    report = catalog.audit()
    records = {Path(s["path"]).name: s for s in report["scripts"]}
    assert report["tracked_active_directory_py"] >= 65
    assert report["tracked_archive_py"] >= 1
    for expected in (
        "parse_wednesday_notice.py",
        "parse_sunday_notice.py",
        "start_friday_zoom_week.py",
        "register_wednesday_song.py",
        "complete_sunday_week.py",
    ):
        assert "referenced_by_root_cli_chain" in records[expected]["evidence"]
    assert "standalone_or_unresolved_static_reference" in (
        records["upload_missing_sources.py"]["evidence"]
    )
    assert records["sync_workspace.py"]["manual_safety_review"]
    assert all(item["delete_without_manual_review"] is False
               for item in records.values())
    assert report["has_deleted_or_changed_any_file"] is False


def test_referenced_script_detection_only_uses_code_string_literals(tmp_path):
    sample = tmp_path / "wednesday.py"
    sample.write_text(
        'a = "parse_wednesday_notice.py"\n'
        '# an unrelated comment can mention upload_missing_sources.py\n',
        encoding="utf-8",
    )
    known = {"parse_wednesday_notice.py", "upload_missing_sources.py"}
    assert catalog.referenced_scripts(sample, known) == {"parse_wednesday_notice.py"}


def test_audit_never_assumes_a_standalone_file_can_be_deleted(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".github/workflows").mkdir(parents=True)
    (tmp_path / "scripts/one.py").write_text("print('safe')\n", encoding="utf-8")
    (tmp_path / "scripts/sync_workspace.py").write_text("print('sample')\n", encoding="utf-8")
    before = (tmp_path / "scripts/one.py").read_bytes()
    report = catalog.audit(tmp_path, paths=[
        "scripts/one.py", "scripts/sync_workspace.py",
    ])
    assert report["standalone_or_unresolved_static_reference"] == 2
    assert report["referenced_by_root_cli_chain"] == 0
    assert not report["static_reference_alone_approves_deletion"]
    assert (tmp_path / "scripts/one.py").read_bytes() == before


def test_scripts_audit_cli_check_reports_only_and_changes_nothing():
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        cwd=ROOT, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert "No repository files or weekly data were changed." in result.stdout
