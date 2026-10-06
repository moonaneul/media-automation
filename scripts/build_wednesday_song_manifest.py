from __future__ import annotations

import argparse
from pathlib import Path

import yaml


FIELD_TO_WEEKLY = {
    "opening_song_1": ("opening_songs", 0),
    "opening_song_2": ("opening_songs", 1),
    "opening_song_3": ("opening_songs", 2),
    "additional_song": ("additional_song", None),
    "decision_hymn": ("decision_hymn", None),
}


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def song_title(weekly, field):
    key, index = FIELD_TO_WEEKLY[field]
    value = weekly[key]
    if index is not None:
        value = value[index]
    if value.get("status") != "VALUE":
        return None
    return value.get("title")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", required=True)
    parser.add_argument("--checklist", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    weekly = load(Path(args.weekly))
    checklist = load(Path(args.checklist))
    output = Path(args.output)

    songs = {}
    for item in checklist.get("items", []):
        field = item.get("field")
        path = item.get("file")
        if field not in FIELD_TO_WEEKLY or not path:
            continue
        title = song_title(weekly, field)
        if not title:
            continue
        songs[title] = {"path": str(Path(path).resolve())}

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump({"songs": songs}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"WEDNESDAY SONG MANIFEST: {output}")


if __name__ == "__main__":
    main()
