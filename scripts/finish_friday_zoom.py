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
        " ".join(str(x) for x in command),
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
        "--weekly",
        required=True,
    )

    parser.add_argument(
        "--bible",
        required=True,
    )

    parser.add_argument(
        "--checklist",
        required=True,
    )

    parser.add_argument(
        "--include-pre-service-audio",
        action="store_true",
    )

    args = parser.parse_args()

    weekly_path = Path(
        args.weekly
    )

    bible_path = Path(
        args.bible
    )

    checklist_path = Path(
        args.checklist
    )

    for path in (
        weekly_path,
        bible_path,
        checklist_path,
    ):
        if not path.exists():
            raise SystemExit(
                f"ERROR: file not found: {path}"
            )

    weekly = load(
        weekly_path
    )

    date_value = str(
        weekly["date"]
    )

    token = date_value.replace(
        "-",
        "",
    )

    # --------------------------------------------------------
    # 1. Media checklist completeness
    # --------------------------------------------------------

    checklist = load(
        checklist_path
    )

    missing = [
        item
        for item in checklist.get(
            "items",
            []
        )
        if not item.get(
            "file"
        )
    ]

    if missing:
        print()
        print(
            "FRIDAY ZOOM BUILD: NOT READY"
        )
        print(
            "=" * 68
        )

        for item in missing:
            field = item[
                "field"
            ]

            title = item.get(
                "title"
            )

            if title:
                print(
                    f"MISSING: {field} "
                    f"({title})"
                )
            else:
                print(
                    f"MISSING: {field}"
                )

        print()
        print(
            "PPT was not generated."
        )

        raise SystemExit(2)

    # --------------------------------------------------------
    # 2. Draft -> final weekly + media manifest
    # --------------------------------------------------------

    run(
        [
            sys.executable,
            "scripts/finalize_friday_zoom_inputs.py",
            "--weekly",
            str(weekly_path),
            "--checklist",
            str(checklist_path),
        ]
    )

    final_weekly = Path(
        f"output/friday-zoom-{token}-final.yaml"
    )

    media_manifest = Path(
        f"output/friday-zoom-{token}-media.yaml"
    )

    if not final_weekly.exists():
        raise SystemExit(
            f"ERROR: final weekly missing: "
            f"{final_weekly}"
        )

    if not media_manifest.exists():
        raise SystemExit(
            f"ERROR: media manifest missing: "
            f"{media_manifest}"
        )

    # --------------------------------------------------------
    # 3. Build PPT
    # --------------------------------------------------------

    pptx = Path(
        f"output/friday_zoom_{token}_final.pptx"
    )

    command = [
        sys.executable,
        "scripts/build_friday_zoom.py",
        "--weekly",
        str(final_weekly),
        "--bible",
        str(bible_path),
        "--media",
        str(media_manifest),
        "--output",
        str(pptx),
    ]

    if args.include_pre_service_audio:
        command.append(
            "--include-pre-service-audio"
        )

    run(
        command
    )

    # --------------------------------------------------------
    # 4. Automated QA
    # --------------------------------------------------------

    run(
        [
            sys.executable,
            "scripts/qa_friday_zoom.py",
            "--pptx",
            str(pptx),
            "--weekly",
            str(final_weekly),
            "--bible",
            str(bible_path),
            "--media",
            str(media_manifest),
        ]
    )

    # --------------------------------------------------------
    # 5. Regression tests
    # --------------------------------------------------------

    run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
        ]
    )

    print()
    print(
        "=" * 68
    )
    print(
        "FRIDAY ZOOM BUILD PIPELINE: PASS"
    )
    print(
        "=" * 68
    )
    print(
        f"date   : {date_value}"
    )
    print(
        f"weekly : {final_weekly}"
    )
    print(
        f"bible  : {bible_path}"
    )
    print(
        f"media  : {media_manifest}"
    )
    print(
        f"pptx   : {pptx}"
    )
    print()
    print(
        "NEXT: actual PowerPoint playback check"
    )


if __name__ == "__main__":
    main()
