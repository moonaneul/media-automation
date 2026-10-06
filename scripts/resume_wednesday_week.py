from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTAKE_DIR = ROOT / "output" / "wednesday_intake"
SONG_ROOT = ROOT / "input" / "wednesday"


def token(date: str) -> str:
    return date.replace("-", "").replace(".", "").strip()


def run(name: str, *args: str, allow=(0,)):
    command = [sys.executable, str(ROOT / "scripts" / name), *args]
    print("\n>>>", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode not in allow:
        raise SystemExit(result.returncode)
    return result.returncode


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def rebuild_derivatives(intake_path: Path, date_token: str):
    intake = load(intake_path)
    fields = intake["fields"]

    bible_requests = []
    for field in ("scripture", "additional_scripture"):
        record = fields[field]
        if record["status"] == "provided" and record.get("value"):
            bible_requests.append(
                {
                    "source": field,
                    "reference": record["value"],
                    "translation": "개역개정",
                    "display_rule": "세례→침례",
                }
            )

    slots = [
        ("opening_song_1", "opening_song_1.pptx"),
        ("opening_song_2", "opening_song_2.pptx"),
        ("opening_song_3", "opening_song_3.pptx"),
        ("additional_song", "additional_song.pptx"),
        ("decision_hymn", "decision_hymn.pptx"),
    ]
    items = []
    for field, filename in slots:
        record = fields[field]
        if record["status"] == "provided" and record.get("value"):
            items.append(
                {
                    "field": field,
                    "title": record["value"],
                    "expected_filename": filename,
                    "file": None,
                }
            )

    (INTAKE_DIR / f"wednesday_{date_token}_bible_requests.yaml").write_text(
        yaml.safe_dump({"requests": bible_requests}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (INTAKE_DIR / f"wednesday_{date_token}_song_checklist.yaml").write_text(
        yaml.safe_dump({"items": items}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    date_token = token(args.date)
    intake = INTAKE_DIR / f"wednesday_{date_token}_intake.yaml"
    if not intake.exists():
        raise SystemExit(f"ERROR: intake not found: {intake}")

    data = load(intake)
    if data.get("review_required"):
        print("REVIEW REQUIRED")
        for item in data.get("review_items", []):
            print(f"  - {item}")
        raise SystemExit(3)

    rebuild_derivatives(intake, date_token)

    weekly = INTAKE_DIR / f"wednesday-{date_token}.yaml"
    bible_requests = INTAKE_DIR / f"wednesday_{date_token}_bible_requests.yaml"
    bible = INTAKE_DIR / f"wednesday-{date_token}-bible.yaml"
    checklist = INTAKE_DIR / f"wednesday_{date_token}_song_checklist.yaml"
    manifest = INTAKE_DIR / f"wednesday-{date_token}-songs.yaml"
    song_dir = SONG_ROOT / date_token

    run(
        "intake_to_wednesday_weekly.py",
        "--intake", str(intake),
        "--output", str(weekly),
        allow=(0, 2, 3),
    )
    run("build_bible_library.py")
    run(
        "resolve_friday_zoom_bible.py",
        "--requests", str(bible_requests),
        "--output", str(bible),
    )
    run(
        "refresh_wednesday_song_checklist.py",
        "--checklist", str(checklist),
        "--song-dir", str(song_dir),
        allow=(0, 2),
    )
    run(
        "build_wednesday_song_manifest.py",
        "--weekly", str(weekly),
        "--checklist", str(checklist),
        "--output", str(manifest),
    )

    print("\n=== WEDNESDAY READY ===")
    print(f"weekly   : {weekly}")
    print(f"bible    : {bible}")
    print(f"songs    : {manifest}")
    print(f"song dir : {song_dir}")


if __name__ == "__main__":
    main()
