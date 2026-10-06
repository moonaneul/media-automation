from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


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


def normalize_token(value):
    return (
        str(value)
        .replace("-", "")
        .replace(".", "")
        .strip()
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
        "--date",
        required=True,
        help=(
            "YYYY-MM-DD 또는 YYYYMMDD"
        ),
    )

    args = parser.parse_args()

    token = normalize_token(
        args.date
    )

    intake_dir = Path(
        "output/friday_zoom_intake"
    )

    weekly = (
        intake_dir
        / f"friday-zoom-{token}.yaml"
    )

    bible = (
        intake_dir
        / f"friday-zoom-{token}-bible.yaml"
    )

    checklist = (
        intake_dir
        / (
            f"friday_zoom_{token}"
            "_media_checklist.yaml"
        )
    )

    media_dir = (
        Path("input/friday_zoom")
        / token
    )

    for path in (
        weekly,
        bible,
        checklist,
        media_dir,
    ):
        if not path.exists():
            raise SystemExit(
                f"ERROR: required input missing: {path}"
            )

    # 1. 폴더 파일 -> checklist 자동 연결
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

    # 2. 예배 전 음원 존재 여부 확인
    checklist_data = load(
        checklist
    )

    pre_service_ready = any(
        item.get("field")
        == "pre_service_audio"
        and item.get("file")
        for item in checklist_data.get(
            "items",
            []
        )
    )

    # 3. FINAL weekly/manifest -> PPT -> QA -> pytest
    command = [
        sys.executable,
        "scripts/finish_friday_zoom.py",
        "--weekly",
        str(weekly),
        "--bible",
        str(bible),
        "--checklist",
        str(checklist),
    ]

    if pre_service_ready:
        command.append(
            "--include-pre-service-audio"
        )

    run(
        command
    )

    pptx = Path(
        f"output/friday_zoom_{token}_final.pptx"
    )

    print()
    print(
        "=" * 68
    )
    print(
        "FRIDAY ZOOM WEEK COMPLETE"
    )
    print(
        "=" * 68
    )
    print(
        f"pptx : {pptx}"
    )
    print()
    print(
        "Remaining manual QA:"
    )
    print(
        "  - video playback"
    )
    print(
        "  - audio autoplay"
    )
    print(
        "  - prayer click animations"
    )


if __name__ == "__main__":
    main()
