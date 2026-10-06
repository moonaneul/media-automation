from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(".")
INTAKE_DIR = Path(
    "output/friday_zoom_intake"
)


def run(*parts):
    command = [
        str(part)
        for part in parts
    ]

    print()
    print(
        ">>>",
        " ".join(command),
    )

    result = subprocess.run(
        command,
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            result.returncode
        )


def newest_intake():
    files = sorted(
        INTAKE_DIR.glob(
            "friday_zoom_*_intake.yaml"
        ),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not files:
        raise SystemExit(
            "ERROR: intake YAML not generated"
        )

    return files[0]


def load(path):
    return yaml.safe_load(
        path.read_text(
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

    # --------------------------------------------------------
    # 1. Bible library refresh
    # --------------------------------------------------------

    run(
        sys.executable,
        "scripts/build_bible_library.py",
    )

    # --------------------------------------------------------
    # 2. Notice -> intake / bible requests / media checklist
    # --------------------------------------------------------

    run(
        sys.executable,
        "scripts/parse_friday_zoom_notice.py",
        "--input",
        notice,
    )

    intake = newest_intake()

    intake_data = load(
        intake
    )

    date_record = intake_data.get(
        "date",
        {}
    )

    if (
        date_record.get("status")
        != "provided"
    ):
        raise SystemExit(
            "ERROR: date was not resolved"
        )

    date_value = str(
        date_record["value"]
    )

    token = date_value.replace(
        "-",
        "",
    )

    # --------------------------------------------------------
    # 3. Intake -> draft weekly
    # --------------------------------------------------------

    weekly = (
        INTAKE_DIR
        / f"friday-zoom-{token}.yaml"
    )

    run(
        sys.executable,
        "scripts/intake_to_friday_zoom_weekly.py",
        "--intake",
        intake,
        "--output",
        weekly,
    )

    # --------------------------------------------------------
    # 4. Bible request -> Bible YAML
    # --------------------------------------------------------

    bible_requests = (
        INTAKE_DIR
        / (
            f"friday_zoom_{token}"
            "_bible_requests.yaml"
        )
    )

    bible_output = (
        INTAKE_DIR
        / f"friday-zoom-{token}-bible.yaml"
    )

    run(
        sys.executable,
        "scripts/resolve_friday_zoom_bible.py",
        "--requests",
        bible_requests,
        "--output",
        bible_output,
    )

    # --------------------------------------------------------
    # 5. Media checklist
    # --------------------------------------------------------

    checklist = (
        INTAKE_DIR
        / (
            f"friday_zoom_{token}"
            "_media_checklist.yaml"
        )
    )

    if not checklist.exists():
        raise SystemExit(
            f"ERROR: media checklist missing: "
            f"{checklist}"
        )

    checklist_data = load(
        checklist
    )

    missing_media = [
        item
        for item
        in checklist_data.get(
            "items",
            []
        )
        if not item.get("file")
    ]

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print()
    print(
        "=" * 68
    )
    print(
        "FRIDAY ZOOM PREPARE: PASS"
    )
    print(
        "=" * 68
    )

    print(
        f"date       : {date_value}"
    )
    print(
        f"intake     : {intake}"
    )
    print(
        f"weekly     : {weekly}"
    )
    print(
        f"bible      : {bible_output}"
    )
    print(
        f"checklist  : {checklist}"
    )

    print()

    if missing_media:
        print(
            "NEXT: media files required"
        )

        for item in missing_media:
            title = item.get(
                "title"
            )

            if title:
                print(
                    f"  - {item['field']}: "
                    f"{title}"
                )
            else:
                print(
                    f"  - {item['field']}"
                )

        print()
        print(
            "PPT build has NOT been started."
        )
        print(
            "No historical media was substituted."
        )

    else:
        print(
            "MEDIA: all checklist entries ready"
        )


if __name__ == "__main__":
    main()
