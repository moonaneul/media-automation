"""Synthetic file-only tests; no church originals or operating DB required."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import zipfile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "device_transfer.py"
spec = spec_from_file_location("device_transfer", SCRIPT)
tool = module_from_spec(spec)
spec.loader.exec_module(tool)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "sources").mkdir()
    (root / "sources" / "original.txt").write_text("source", encoding="utf-8")
    (root / "input").mkdir()
    (root / "input" / "수요예배.txt").write_text("input", encoding="utf-8")
    (root / "data" / "private").mkdir(parents=True)
    (root / "data" / "private" / "bible.json").write_text("{}", encoding="utf-8")
    (root / "output").mkdir()
    (root / "output" / "obsolete.pptx").write_bytes(b"DO NOT TRANSFER")
    (root / ".env").write_text("FAKE_ONLY", encoding="utf-8")
    return root


def test_pack_verify_and_import_dont_transfer_outputs_or_credentials(project, tmp_path):
    bundle = tmp_path / "data.zip"
    result = tool.pack(project, bundle)
    assert result["files"] == 3
    records, checked = tool.verify(bundle)
    assert checked["mode"] == "VERIFIED"
    assert {rec["path"] for rec in records} == {
        "sources/original.txt", "input/수요예배.txt", "data/private/bible.json"
    }
    with zipfile.ZipFile(bundle) as archive:
        assert "output/obsolete.pptx" not in archive.namelist()
        assert ".env" not in archive.namelist()

    dest = tmp_path / "mac"
    dest.mkdir()
    assert tool.import_inputs(bundle, dest)["copy_candidates"] == 3
    done = tool.import_inputs(bundle, dest, copy=True)
    assert done["copied"] == 3
    assert not (dest / "output").exists()
    assert not (dest / ".env").exists()
    assert tool.import_inputs(bundle, dest)["identical_files"] == 3


def test_conflict_is_reported_and_never_overwritten(project, tmp_path):
    bundle = tmp_path / "data.zip"
    tool.pack(project, bundle)
    dest = tmp_path / "mac"
    (dest / "input").mkdir(parents=True)
    existing = dest / "input" / "수요예배.txt"
    existing.write_text("MAC UNIQUE", encoding="utf-8")
    assert tool.import_inputs(bundle, dest)["conflicts"] == 1
    with pytest.raises(ValueError):
        tool.import_inputs(bundle, dest, copy=True)
    assert existing.read_text(encoding="utf-8") == "MAC UNIQUE"
    assert not (dest / "sources" / "original.txt").exists()


def test_zip_cannot_overwrite_existing_bundle(project, tmp_path):
    bundle = tmp_path / "data.zip"
    bundle.write_bytes(b"EXISTING")
    with pytest.raises(ValueError):
        tool.pack(project, bundle)
    assert bundle.read_bytes() == b"EXISTING"


def test_blocked_input_causes_explicit_failure(project, tmp_path):
    (project / "input" / ".env.local").write_text("fake", encoding="utf-8")
    with pytest.raises(ValueError):
        tool.pack(project, tmp_path / "data.zip")


def test_tampered_archive_is_rejected(project, tmp_path):
    bundle = tmp_path / "data.zip"
    tool.pack(project, bundle)
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bundle) as orig, zipfile.ZipFile(bad, "w") as modified:
        for name in orig.namelist():
            payload = orig.read(name)
            if name == "sources/original.txt":
                payload = b"REPLACED"
            modified.writestr(name, payload)
    with pytest.raises(ValueError):
        tool.verify(bad)


def test_unexpected_entry_and_traversal_are_rejected(project, tmp_path):
    bundle = tmp_path / "data.zip"
    tool.pack(project, bundle)
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bundle) as orig, zipfile.ZipFile(bad, "w") as modified:
        for name in orig.namelist():
            modified.writestr(name, orig.read(name))
        modified.writestr("../escape", "unsafe")
    with pytest.raises(ValueError):
        tool.verify(bad)
    assert not tool.allowed("input/../../oops")
    assert not tool.allowed("output/obsolete.pptx")


def test_symlinked_input_is_not_silently_exported(project, tmp_path):
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    try:
        (project / "input" / "shortcut").symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("This machine does not allow symlinks")
    with pytest.raises(ValueError):
        tool.pack(project, tmp_path / "data.zip")
