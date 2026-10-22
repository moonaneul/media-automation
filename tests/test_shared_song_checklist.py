"""No-source, synthetic CLI tests for the two weekly score checklist tools."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from media_automation.weekly_song_checklist import refresh_exact_song_files


ROOT = Path(__file__).resolve().parents[1]


def _item(name, *, filename=None, existing="manually-registered-score.pptx"):
    return {
        "field": name,
        "title": "합성 테스트 곡",
        "expected_filename": filename,
        "file": existing,
    }


def test_refresh_exact_checklist_never_inherits_stale_file_or_guesses_similar_names(tmp_path):
    song_dir = tmp_path / "sunday"
    song_dir.mkdir()
    (song_dir / "actual.pptx").write_bytes(b"SYNTHETIC SCORE PLACEHOLDER")
    (song_dir / "similar.pptx").write_bytes(b"SIMILAR FILE MUST NOT SUBSTITUTE")
    old = {
        "items": [
            _item("opening_song_1", filename="actual.pptx"),
            _item("opening_song_2", filename="similar-other.pptx"),
            _item("opening_song_3", filename=None),
        ],
        "extra": {"service": "sunday", "state": "NONE"},
    }
    data = deepcopy(old)
    items = refresh_exact_song_files(data, song_dir)
    assert items[0]["file"] == str(song_dir / "actual.pptx")
    assert items[1]["file"] is None
    # An unspecified filename preserves the explicitly registered choice; do not guess.
    assert items[2]["file"] == "manually-registered-score.pptx"
    assert data["extra"] == old["extra"]
    assert all((song_dir / item).exists() for item in ("actual.pptx", "similar.pptx"))


@pytest.mark.parametrize("service", ["wednesday", "sunday"])
def test_both_legacy_cli_paths_update_only_exact_names_and_return_missing_code(tmp_path, service):
    folder = tmp_path / service
    folder.mkdir()
    (folder / "confirmed.pptx").write_bytes(b"SYNTHETIC ONLY")
    (folder / "lookalike.pptx").write_bytes(b"WRONG SONG")
    checklist = tmp_path / (service + ".yaml")
    checklist.write_text(
        yaml.safe_dump(
            {"items": [
                _item("opening_song_1", filename="confirmed.pptx"),
                _item("opening_song_2", filename="unprovided.pptx"),
            ], "still_here": {"state": "NONE"}},
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / f"refresh_{service}_song_checklist.py"),
            "--checklist", str(checklist),
            "--song-dir", str(folder),
        ], capture_output=True, text=True, cwd=ROOT, timeout=20,
        check=False,
    )
    assert result.returncode == 2, result.stderr
    assert "READY" in result.stdout and "MISSING" in result.stdout
    assert "자동 대체하지 않습니다" in result.stdout
    updated = yaml.safe_load(checklist.read_text(encoding="utf-8"))
    assert updated["items"][0]["file"] == str(folder / "confirmed.pptx")
    assert updated["items"][1]["file"] is None
    assert updated["still_here"] == {"state": "NONE"}
    assert (folder / "lookalike.pptx").read_bytes() == b"WRONG SONG"


@pytest.mark.parametrize("service", ["wednesday", "sunday"])
def test_cli_exact_match_passes_without_creating_unrequested_score(tmp_path, service):
    folder = tmp_path / service
    folder.mkdir()
    (folder / "only.pptx").write_bytes(b"SYNTHETIC CONTENT")
    checklist = tmp_path / "checklist.yaml"
    checklist.write_text(
        yaml.safe_dump({"items": [_item("opening_song_1", filename="only.pptx")]}),
        encoding="utf-8",
    )
    before = {p.name for p in folder.iterdir()}
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / f"refresh_{service}_song_checklist.py"),
            "--checklist", str(checklist), "--song-dir", str(folder)
        ], capture_output=True, text=True, cwd=ROOT, timeout=20,
    )
    assert result.returncode == 0, result.stderr
    assert {p.name for p in folder.iterdir()} == before
