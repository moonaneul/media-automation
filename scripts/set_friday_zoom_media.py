from __future__ import annotations

import argparse
from pathlib import Path

import yaml


VIDEO_FIELDS = {
    "opening_song_1",
    "opening_song_2",
    "song_after_prayer",
    "response_song",
    "intercession_song",
}

AUDIO_FIELDS = {
    "first_prayer",
    "word_prayer",
    "community_prayer",
    "personal_prayer",
    "pre_service_audio",
}

VIDEO_EXTENSIONS = {
    ".mp4",
    ".wmv",
    ".mov",
    ".m4v",
}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".aac",
}


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--checklist",
        required=True,
    )

    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="FIELD=FILE",
    )

    parser.add_argument(
        "--show",
        action="store_true",
    )

    return parser.parse_args()


def load_yaml(path: Path):
    return yaml.safe_load(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def normalize_path(
    file_path: Path,
) -> str:
    file_path = file_path.resolve()

    output_dir = Path(
        "output"
    ).resolve()

    try:
        relative = file_path.relative_to(
            output_dir
        )

        return relative.as_posix()

    except ValueError:
        return str(file_path)


def expected_type(field: str):
    if field in VIDEO_FIELDS:
        return "video"

    if field in AUDIO_FIELDS:
        return "audio"

    raise ValueError(
        f"unknown media field: {field}"
    )


def validate_file(
    field: str,
    file_path: Path,
):
    if not file_path.exists():
        raise ValueError(
            f"file not found: {file_path}"
        )

    if not file_path.is_file():
        raise ValueError(
            f"not a file: {file_path}"
        )

    extension = (
        file_path.suffix.lower()
    )

    media_type = expected_type(
        field
    )

    if (
        media_type == "video"
        and extension
        not in VIDEO_EXTENSIONS
    ):
        raise ValueError(
            f"{field} requires video, "
            f"got {extension}"
        )

    if (
        media_type == "audio"
        and extension
        not in AUDIO_EXTENSIONS
    ):
        raise ValueError(
            f"{field} requires audio, "
            f"got {extension}"
        )


def show(data):
    print()
    print(
        "=== Friday Zoom Media Checklist ==="
    )

    items = data.get(
        "items",
        []
    )

    for item in items:
        field = item.get(
            "field",
            ""
        )

        media_type = item.get(
            "media_type",
            ""
        )

        title = item.get(
            "title",
            ""
        )

        file_value = item.get(
            "file"
        )

        status = (
            "READY"
            if file_value
            else "MISSING"
        )

        print()
        print(
            f"[{status}] {field}"
        )

        print(
            f"  type : {media_type}"
        )

        if title:
            print(
                f"  title: {title}"
            )

        print(
            f"  file : "
            f"{file_value or '-'}"
        )

        if (
            "permission_confirmed"
            in item
        ):
            print(
                "  usage permission confirmed: "
                f"{item['permission_confirmed']}"
            )


def main():
    args = parse_args()

    checklist_path = Path(
        args.checklist
    )

    data = load_yaml(
        checklist_path
    )

    items = data.setdefault(
        "items",
        []
    )

    item_by_field = {
        item["field"]: item
        for item in items
    }

    changed = False

    for expression in args.set:
        if "=" not in expression:
            raise SystemExit(
                "ERROR: --set must be FIELD=FILE"
            )

        field, raw_path = (
            expression.split(
                "=",
                1,
            )
        )

        field = field.strip()
        raw_path = raw_path.strip()

        if not field:
            raise SystemExit(
                "ERROR: empty field"
            )

        if not raw_path:
            raise SystemExit(
                f"ERROR: empty path for {field}"
            )

        if (
            field
            not in VIDEO_FIELDS
            and field
            not in AUDIO_FIELDS
        ):
            raise SystemExit(
                f"ERROR: unknown field: {field}"
            )

        if field not in item_by_field:
            # pre-service audio is optional,
            # so it may not exist in the original checklist.
            if field == "pre_service_audio":
                item = {
                    "field":
                        "pre_service_audio",
                    "media_type":
                        "audio",
                    "file":
                        None,
                }

                items.append(
                    item
                )

                item_by_field[
                    field
                ] = item

            else:
                raise SystemExit(
                    f"ERROR: field not present "
                    f"in this week's checklist: "
                    f"{field}"
                )

        file_path = Path(
            raw_path
        )

        try:
            validate_file(
                field,
                file_path,
            )
        except ValueError as exc:
            raise SystemExit(
                f"ERROR: {exc}"
            )

        stored_path = normalize_path(
            file_path
        )

        item = item_by_field[
            field
        ]

        item["media_type"] = (
            expected_type(
                field
            )
        )

        item["file"] = stored_path

        changed = True

        print(
            f"OK: {field} -> {stored_path}"
        )

    if changed:
        checklist_path.write_text(
            yaml.safe_dump(
                data,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

        print()
        print(
            f"UPDATED: {checklist_path}"
        )

    if args.show or not args.set:
        show(
            data
        )


if __name__ == "__main__":
    main()
