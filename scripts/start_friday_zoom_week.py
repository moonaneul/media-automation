from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


INTAKE_DIR = Path(
    "output/friday_zoom_intake"
)


def run(command):
    print()
    print(
        ">>>",
        " ".join(
            str(x)
            for x in command
        ),
    )

    result = subprocess.run(
        command,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            result.returncode
        )


def load(path):
    return yaml.safe_load(
        Path(path).read_text(
            encoding="utf-8-sig"
        )
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--notice",
        required=True,
    )

    args = parser.parse_args()

    notice = Path(
        args.notice
    )

    if not notice.exists():
        raise SystemExit(
            f"ERROR: notice not found: {notice}"
        )

    # 1. 안내문 -> intake/weekly/bible/checklist
    run(
        [
            sys.executable,
            "scripts/prepare_friday_zoom.py",
            "--notice",
            str(notice),
        ]
    )

    # 방금 생성된 intake 확인
    intake_files = sorted(
        INTAKE_DIR.glob(
            "friday_zoom_*_intake.yaml"
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not intake_files:
        raise SystemExit(
            "ERROR: intake not generated"
        )

    intake = intake_files[0]

    data = load(
        intake
    )

    date_value = str(
        data["date"]["value"]
    )

    token = date_value.replace(
        "-",
        "",
    )

    checklist = (
        INTAKE_DIR
        / (
            f"friday_zoom_{token}"
            "_media_checklist.yaml"
        )
    )

    media_dir = (
        Path("input/friday_zoom")
        / token
    )

    # 2. 이번 주 미디어 폴더 생성
    run(
        [
            sys.executable,
            "scripts/link_friday_zoom_media_folder.py",
            "--checklist",
            str(checklist),
            "--media-dir",
            str(media_dir),
        ]
    )

    print()
    print(
        "=" * 68
    )
    print(
        "FRIDAY ZOOM WEEK STARTED"
    )
    print(
        "=" * 68
    )
    print(
        f"date      : {date_value}"
    )
    print(
        f"media dir : {media_dir}"
    )
    print()
    print(
        "NEXT: put this week's MP4/MP3 files "
        "into the media folder."
    )
    print()
    print(
        "Do not run this start command again "
        "after media linking unless you intend "
        "to recreate the weekly input files."
    )


if __name__ == "__main__":
    main()
