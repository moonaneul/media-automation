from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_explicit_shared_community_personal_audio(tmp_path):
    checklist = tmp_path / "checklist.yaml"
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    checklist.write_text(
        yaml.safe_dump(
            {
                "items": [
                    {
                        "field": "community_prayer",
                        "media_type": "audio",
                        "file": None,
                    },
                    {
                        "field": "personal_prayer",
                        "media_type": "audio",
                        "file": None,
                    },
                ]
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    shared = media_dir / "community_personal_prayer.mp3"
    shared.write_bytes(b"test")

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "link_friday_zoom_media_folder.py"),
            "--checklist",
            str(checklist),
            "--media-dir",
            str(media_dir),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr

    data = yaml.safe_load(
        checklist.read_text(encoding="utf-8")
    )

    files = {
        item["field"]: item["file"]
        for item in data["items"]
    }

    assert files["community_prayer"] == str(shared.resolve())
    assert files["personal_prayer"] == str(shared.resolve())
