from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml


SONG_FIELDS = {
    "opening_song_1": ("opening_songs", 0, "opening_songs[0]"),
    "opening_song_2": ("opening_songs", 1, "opening_songs[1]"),
    "song_after_prayer": ("song_after_prayer", None, "song_after_prayer"),
    "response_song": ("response_song", None, "response_song"),
    "intercession_song": ("intercession_song", None, "intercession_song"),
}

AUDIO_FIELDS = {
    "first_prayer": "first_prayer_audio",
    "word_prayer": "word_prayer_audio",
    "community_prayer": "community_prayer_audio",
    "personal_prayer": "personal_prayer_audio",
}


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument(
        "--weekly",
        required=True,
    )

    p.add_argument(
        "--checklist",
        required=True,
    )

    p.add_argument(
        "--schema",
        default="samples/weekly/friday-zoom-20260918.yaml",
    )

    return p.parse_args()


def load(path):
    return yaml.safe_load(
        Path(path).read_text(
            encoding="utf-8-sig"
        )
    )


def get_song(weekly, field):
    key, index, _ = SONG_FIELDS[field]

    if index is None:
        return weekly[key]

    return weekly[key][index]


def get_schema_song(schema, field):
    key, index, _ = SONG_FIELDS[field]

    if index is None:
        return schema[key]

    return schema[key][index]


def main():
    args = parse_args()

    weekly = load(args.weekly)
    checklist = load(args.checklist)
    schema = load(args.schema)

    items = {
        item["field"]: item
        for item in checklist.get(
            "items",
            []
        )
    }

    failures = []

    date_value = str(
        weekly["date"]
    )

    token = date_value.replace(
        "-",
        "",
    )

    output_dir = Path("output")

    final_weekly_path = (
        output_dir
        / f"friday-zoom-{token}-final.yaml"
    )

    manifest_path = (
        output_dir
        / f"friday-zoom-{token}-media.yaml"
    )

    manifest = {
        "media": {}
    }

    # --------------------------------------------------------
    # Songs
    # --------------------------------------------------------

    for field, (
        weekly_key,
        index,
        manifest_key,
    ) in SONG_FIELDS.items():

        song = get_song(
            weekly,
            field,
        )

        if (
            not isinstance(song, dict)
            or song.get("status") != "VALUE"
        ):
            continue

        item = items.get(field)

        if not item:
            failures.append(
                f"{field}: checklist entry missing"
            )
            continue

        expected_title = str(
            song.get(
                "title",
                "",
            )
        ).strip()

        checklist_title = str(
            item.get(
                "title",
                "",
            )
        ).strip()

        if (
            expected_title
            != checklist_title
        ):
            failures.append(
                f"{field}: title mismatch "
                f"weekly={expected_title!r} "
                f"checklist={checklist_title!r}"
            )
            continue

        file_value = item.get(
            "file"
        )

        if not file_value:
            failures.append(
                f"{field}: media file not selected"
            )
            continue

        file_value = str(
            file_value
        )

        file_path = Path(
            file_value
        )

        # Existing manifests use paths relative to output/.
        resolved = (
            file_path
            if file_path.is_absolute()
            else output_dir / file_path
        )

        if not resolved.exists():
            failures.append(
                f"{field}: file not found: "
                f"{resolved}"
            )
            continue

        schema_song = get_schema_song(
            schema,
            field,
        )

        media_meta = copy.deepcopy(
            schema_song.get(
                "media",
                {},
            )
        )

        # Only reusable media-state structure is inherited.
        # No historical file or song content is copied.
        media_meta["status"] = "VALUE"
        media_meta[
            "file_status"
        ] = "AVAILABLE"

        song["media"] = media_meta

        manifest["media"][
            manifest_key
        ] = {
            "type": "video",
            "title": expected_title,
            "path": file_value,
        }

    # --------------------------------------------------------
    # Prayer audio
    # --------------------------------------------------------

    for field, manifest_key in (
        AUDIO_FIELDS.items()
    ):
        prayer = weekly.get(
            field
        )

        if (
            not isinstance(prayer, dict)
            or prayer.get("status")
            != "VALUE"
        ):
            continue

        item = items.get(field)

        if not item:
            failures.append(
                f"{field}: checklist entry missing"
            )
            continue

        file_value = item.get(
            "file"
        )

        if not file_value:
            failures.append(
                f"{field}: audio file not selected"
            )
            continue

        file_value = str(
            file_value
        )

        file_path = Path(
            file_value
        )

        resolved = (
            file_path
            if file_path.is_absolute()
            else output_dir / file_path
        )

        if not resolved.exists():
            failures.append(
                f"{field}: file not found: "
                f"{resolved}"
            )
            continue

        manifest["media"][
            manifest_key
        ] = {
            "type": "audio",
            "path": file_value,
        }

    # --------------------------------------------------------
    # Optional pre-service audio
    # --------------------------------------------------------

    pre_service = items.get(
        "pre_service_audio"
    )

    if (
        pre_service
        and pre_service.get("file")
    ):
        file_value = str(
            pre_service["file"]
        )

        file_path = Path(
            file_value
        )

        resolved = (
            file_path
            if file_path.is_absolute()
            else output_dir / file_path
        )

        if not resolved.exists():
            failures.append(
                "pre_service_audio: "
                f"file not found: {resolved}"
            )
        else:
            manifest["media"][
                "pre_service_audio"
            ] = {
                "type": "audio",
                "path": file_value,
            }

    # --------------------------------------------------------
    # Stop before writing invalid FINAL files
    # --------------------------------------------------------

    if failures:
        print()
        print(
            "FRIDAY ZOOM FINALIZE: NOT READY"
        )
        print(
            "=" * 60
        )

        for failure in failures:
            print(
                "MISSING:",
                failure,
            )

        print()
        print(
            "No historical media was substituted."
        )

        raise SystemExit(2)

    final_weekly_path.write_text(
        yaml.safe_dump(
            weekly,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    manifest_path.write_text(
        yaml.safe_dump(
            manifest,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "FRIDAY ZOOM FINALIZE: PASS"
    )
    print(
        "=" * 60
    )
    print(
        f"weekly : {final_weekly_path}"
    )
    print(
        f"media  : {manifest_path}"
    )


if __name__ == "__main__":
    main()
