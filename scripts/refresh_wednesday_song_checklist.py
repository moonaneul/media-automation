from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checklist", required=True)
    parser.add_argument("--song-dir", required=True)
    args = parser.parse_args()

    checklist_path = Path(args.checklist)
    song_dir = Path(args.song_dir)
    song_dir.mkdir(parents=True, exist_ok=True)

    data = load(checklist_path)
    items = data.get("items", [])

    for item in items:
        expected = item.get("expected_filename")
        if not expected:
            continue
        candidate = song_dir / expected
        item["file"] = str(candidate) if candidate.is_file() else None

    checklist_path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    missing = [item for item in items if not item.get("file")]

    print("\n=== Wednesday Song Checklist ===")
    for item in items:
        state = "READY" if item.get("file") else "MISSING"
        print(f"{state:7} {item['field']}: {item.get('title', '')}")

    if missing:
        print("\n누락 악보는 비슷한 파일명이나 과거 주차 자료로 자동 대체하지 않습니다.")
        raise SystemExit(2)


if __name__ == "__main__":
    main()
