from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

import yaml


SLOTS = {
    "opening_song_1": {
        "type": "video",
        "extensions": [".mp4", ".wmv", ".mov", ".m4v"],
    },
    "opening_song_2": {
        "type": "video",
        "extensions": [".mp4", ".wmv", ".mov", ".m4v"],
    },
    "first_prayer": {
        "type": "audio",
        "extensions": [".mp3", ".wav", ".m4a", ".aac"],
    },
    "song_after_prayer": {
        "type": "video",
        "extensions": [".mp4", ".wmv", ".mov", ".m4v"],
    },
    "response_song": {
        "type": "video",
        "extensions": [".mp4", ".wmv", ".mov", ".m4v"],
    },
    "word_prayer": {
        "type": "audio",
        "extensions": [".mp3", ".wav", ".m4a", ".aac"],
    },
    "intercession_song": {
        "type": "video",
        "extensions": [".mp4", ".wmv", ".mov", ".m4v"],
    },
    "community_prayer": {
        "type": "audio",
        "extensions": [".mp3", ".wav", ".m4a", ".aac"],
    },
    "personal_prayer": {
        "type": "audio",
        "extensions": [".mp3", ".wav", ".m4a", ".aac"],
    },
    "pre_service_audio": {
        "type": "audio",
        "extensions": [".mp3", ".wav", ".m4a", ".aac"],
        "optional": True,
    },
}

SHARED_COMMUNITY_PERSONAL_SLOT = (
    "community_personal_prayer"
)
SHARED_COMMUNITY_PERSONAL_FIELDS = {
    "community_prayer",
    "personal_prayer",
}

COMMON_AUDIO_FIELDS = {
    "first_prayer",
    "word_prayer",
    "community_prayer",
    "personal_prayer",
}


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--checklist",
        required=True,
    )

    parser.add_argument(
        "--media-dir",
        required=True,
    )

    parser.add_argument(
        "--common-media-dir",
    )

    return parser.parse_args()


def find_exact_slot_file(
    directory: Path,
    slot: str,
    extensions: list[str],
):
    matches = []

    for extension in extensions:
        candidate = (
            directory
            / f"{slot}{extension}"
        )

        if candidate.exists():
            matches.append(candidate)

    if len(matches) > 1:
        raise SystemExit(
            f"ERROR: multiple files for {slot}: "
            + ", ".join(
                str(path)
                for path in matches
            )
        )

    return (
        matches[0]
        if matches
        else None
    )


def main():
    args = parse_args()

    checklist = Path(
        args.checklist
    )

    media_dir = Path(
        args.media_dir
    )

    common_media_dir = (
        Path(args.common_media_dir)
        if args.common_media_dir
        else None
    )

    if not checklist.exists():
        raise SystemExit(
            f"ERROR: checklist not found: {checklist}"
        )

    if not media_dir.exists():
        media_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            f"CREATED: {media_dir}"
        )
        print()
        print(
            "Put this week's media files "
            "into this folder and run again."
        )

        return

    data = yaml.safe_load(
        checklist.read_text(
            encoding="utf-8-sig"
        )
    ) or {}

    checklist_fields = {
        item.get("field")
        for item in data.get(
            "items",
            []
        )
    }

    shared_audio = find_exact_slot_file(
        media_dir,
        SHARED_COMMUNITY_PERSONAL_SLOT,
        SLOTS["community_prayer"]["extensions"],
    )

    common_shared_audio = None

    if (
        common_media_dir is not None
        and common_media_dir.exists()
    ):
        common_shared_audio = find_exact_slot_file(
            common_media_dir,
            SHARED_COMMUNITY_PERSONAL_SLOT,
            SLOTS["community_prayer"]["extensions"],
        )

    assignments = []
    missing = []

    for slot, config in (
        SLOTS.items()
    ):
        optional = config.get(
            "optional",
            False,
        )

        # 이번 주 체크리스트에 없는 슬롯은
        # 자동으로 만들거나 승계하지 않는다.
        if (
            slot not in checklist_fields
            and slot != "pre_service_audio"
        ):
            continue

        path = find_exact_slot_file(
            media_dir,
            slot,
            config["extensions"],
        )

        # community/personal 기도에서 같은 음원을
        # 의도적으로 사용할 때만 명시적 공유 파일명을 허용한다.
        # 일반 파일을 비슷하다는 이유로 추정해서 공유하지 않는다.
        if (
            path is None
            and slot in SHARED_COMMUNITY_PERSONAL_FIELDS
            and shared_audio is not None
        ):
            path = shared_audio

        # 공통 음원은 기도 음원에만 fallback으로 사용한다.
        # 항상 이번 주 파일이 공통 파일보다 우선한다.
        if (
            path is None
            and slot in COMMON_AUDIO_FIELDS
            and common_media_dir is not None
            and common_media_dir.exists()
        ):
            path = find_exact_slot_file(
                common_media_dir,
                slot,
                config["extensions"],
            )

        if (
            path is None
            and slot in SHARED_COMMUNITY_PERSONAL_FIELDS
            and common_shared_audio is not None
        ):
            path = common_shared_audio

        if path is None:
            if not optional:
                missing.append(slot)

            continue

        assignments.append(
            (
                slot,
                path,
            )
        )

    if assignments:
        command = [
            sys.executable,
            "scripts/set_friday_zoom_media.py",
            "--checklist",
            str(checklist),
        ]

        for slot, path in assignments:
            command += [
                "--set",
                f"{slot}={path}",
            ]

        print()
        print("=== AUTO MEDIA LINK ===")

        for slot, path in assignments:
            print(
                f"FOUND : {slot:<24} "
                f"{path.name}"
            )

        result = subprocess.run(
            command,
            check=False,
        )

        if result.returncode != 0:
            raise SystemExit(
                result.returncode
            )

    print()
    print(
        "=" * 68
    )

    if missing:
        print(
            "MEDIA FOLDER: NOT READY"
        )

        for slot in missing:
            print(
                f"MISSING: {slot}"
            )

        print()
        print(
            f"folder: {media_dir}"
        )

        print()
        print(
            "No similar filename or historical "
            "media was substituted."
        )

        raise SystemExit(2)

    print(
        "MEDIA FOLDER: READY"
    )
    print(
        f"folder: {media_dir}"
    )


if __name__ == "__main__":
    main()
