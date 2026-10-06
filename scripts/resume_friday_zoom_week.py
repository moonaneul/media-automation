from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


INTAKE_DIR = Path("output/friday_zoom_intake")


SONG_FIELDS = [
    "opening_song_1",
    "opening_song_2",
    "song_after_prayer",
    "response_song",
    "intercession_song",
]

AUDIO_FIELDS = [
    "first_prayer",
    "word_prayer",
    "community_prayer",
    "personal_prayer",
]


def load(path: Path):
    if not path.exists():
        return {}

    return yaml.safe_load(
        path.read_text(
            encoding="utf-8-sig"
        )
    ) or {}


def save(path: Path, data):
    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def normalize_token(value: str):
    return (
        str(value)
        .replace("-", "")
        .replace(".", "")
        .strip()
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


def field_record(
    intake,
    name,
):
    return (
        intake
        .get("fields", {})
        .get(
            name,
            {
                "status": "missing",
                "value": None,
            },
        )
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--date",
        required=True,
    )

    args = parser.parse_args()

    token = normalize_token(
        args.date
    )

    intake_path = (
        INTAKE_DIR
        / f"friday_zoom_{token}_intake.yaml"
    )

    bible_requests_path = (
        INTAKE_DIR
        / (
            f"friday_zoom_{token}"
            "_bible_requests.yaml"
        )
    )

    checklist_path = (
        INTAKE_DIR
        / (
            f"friday_zoom_{token}"
            "_media_checklist.yaml"
        )
    )

    weekly_path = (
        INTAKE_DIR
        / f"friday-zoom-{token}.yaml"
    )

    bible_path = (
        INTAKE_DIR
        / f"friday-zoom-{token}-bible.yaml"
    )

    media_dir = (
        Path("input/friday_zoom")
        / token
    )

    if not intake_path.exists():
        raise SystemExit(
            f"ERROR: intake not found: {intake_path}"
        )

    intake = load(
        intake_path
    )

    # --------------------------------------------------------
    # REVIEW gate
    # --------------------------------------------------------

    if intake.get(
        "review_required",
        False,
    ):
        print()
        print(
            "STOP: REVIEW is still required."
        )

        for item in intake.get(
            "review_items",
            []
        ):
            print(
                f"  REVIEW: {item}"
            )

        raise SystemExit(3)

    print()
    print(
        "PASS: review complete"
    )

    # --------------------------------------------------------
    # Rebuild Bible requests from CURRENT intake
    # --------------------------------------------------------

    bible_requests = {
        "requests": []
    }

    for field in (
        "scripture",
        "additional_scripture",
    ):
        record = field_record(
            intake,
            field,
        )

        if (
            record.get("status")
            != "provided"
        ):
            continue

        reference = record.get(
            "value"
        )

        if not reference:
            continue

        bible_requests[
            "requests"
        ].append(
            {
                "source": field,
                "reference": reference,
                "translation": "개역개정",
                "display_rule": "세례→침례",
            }
        )

    save(
        bible_requests_path,
        bible_requests,
    )

    print(
        "OK: Bible requests synchronized"
    )

    # --------------------------------------------------------
    # Rebuild media checklist from CURRENT intake
    #
    # Existing file links are preserved only when
    # field/title still match.
    # --------------------------------------------------------

    old_checklist = load(
        checklist_path
    )

    old_items = {
        item.get("field"): item
        for item in old_checklist.get(
            "items",
            []
        )
    }

    new_items = []

    for field in SONG_FIELDS:
        record = field_record(
            intake,
            field,
        )

        if (
            record.get("status")
            != "provided"
        ):
            continue

        title = record.get(
            "value"
        )

        if not title:
            continue

        old = old_items.get(
            field,
            {},
        )

        same_title = (
            old.get("title")
            == title
        )

        item = {
            "field": field,
            "title": title,
            "media_type": "video",
            "file": (
                old.get("file")
                if same_title
                else None
            ),
            "permission_confirmed": (
                old.get(
                    "permission_confirmed",
                    False,
                )
                if same_title
                else False
            ),
        }

        new_items.append(
            item
        )

    for field in AUDIO_FIELDS:
        record = field_record(
            intake,
            field,
        )

        if (
            record.get("status")
            != "provided"
        ):
            continue

        old = old_items.get(
            field,
            {},
        )

        new_items.append(
            {
                "field": field,
                "media_type": "audio",
                "file": old.get(
                    "file"
                ),
            }
        )

    # Optional pre-service audio is preserved
    # only when it was explicitly linked before.
    old_pre = old_items.get(
        "pre_service_audio"
    )

    if (
        old_pre
        and old_pre.get("file")
    ):
        new_items.append(
            old_pre
        )

    save(
        checklist_path,
        {
            "items": new_items,
        },
    )

    print(
        "OK: media checklist synchronized"
    )

    # --------------------------------------------------------
    # Current intake -> weekly
    # --------------------------------------------------------

    run(
        [
            sys.executable,
            "scripts/intake_to_friday_zoom_weekly.py",
            "--intake",
            str(intake_path),
            "--output",
            str(weekly_path),
        ]
    )

    # --------------------------------------------------------
    # Refresh verified local Bible library
    # --------------------------------------------------------

    run(
        [
            sys.executable,
            "scripts/build_bible_library.py",
        ]
    )

    # --------------------------------------------------------
    # Resolve Bible
    # --------------------------------------------------------

    run(
        [
            sys.executable,
            "scripts/resolve_friday_zoom_bible.py",
            "--requests",
            str(bible_requests_path),
            "--output",
            str(bible_path),
        ]
    )

    # --------------------------------------------------------
    # Media folder
    # Missing media is NOT a pipeline error here.
    # --------------------------------------------------------

    print()
    print(
        ">>> checking media folder"
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/link_friday_zoom_media_folder.py",
            "--checklist",
            str(checklist_path),
            "--media-dir",
            str(media_dir),
        ],
        check=False,
    )

    if result.returncode not in (
        0,
        2,
    ):
        raise SystemExit(
            result.returncode
        )

    print()
    print(
        "=" * 68
    )
    print(
        "FRIDAY ZOOM RESUME: PASS"
    )
    print(
        "=" * 68
    )
    print(
        f"intake    : {intake_path}"
    )
    print(
        f"weekly    : {weekly_path}"
    )
    print(
        f"bible     : {bible_path}"
    )
    print(
        f"checklist : {checklist_path}"
    )
    print(
        f"media dir : {media_dir}"
    )

    # Reload the checklist after media linking.
    # Determine readiness from actual linked media files.
    refreshed_checklist = load(
        checklist_path
    )

    missing_media = [
        item
        for item in refreshed_checklist.get(
            "items",
            []
        )
        if not item.get("file")
    ]

    if missing_media:
        print()
        print(
            "NEXT: add this week's media files."
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

    else:
        print()
        print(
            "NEXT: run complete_friday_zoom_week.py"
        )


if __name__ == "__main__":
    main()
