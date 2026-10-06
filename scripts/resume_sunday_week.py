from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from media_automation.weekly_data.models import SundayData, WeeklyStatus, parse_weekly_data


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INTAKE_DIR = ROOT / "output" / "sunday_intake"
SONG_ROOT = ROOT / "input" / "sunday"


def run_script(name: str, *args: str, allow=(0,)) -> int:
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    print("\n>>>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode not in allow:
        raise SystemExit(result.returncode)
    return result.returncode


def token(date_value: str) -> str:
    return date_value.replace("-", "").replace(".", "").strip()


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def operational_missing(weekly: SundayData) -> list[str]:
    missing: list[str] = []

    for index, song in enumerate(weekly.worship.opening_songs, start=1):
        if song.status == WeeklyStatus.UNSET:
            missing.append(f"opening_song_{index}")

    checks = (
        ("separate_hymn", weekly.worship.separate_hymn),
        (
            "second_service_prayer",
            weekly.serving.this_week.second_service.prayer,
        ),
        ("church_news", weekly.bulletin.church_news),
        ("offering_hymn", weekly.worship.offering_hymn),
        (
            "second_service_offering_prayer",
            weekly.serving.this_week.second_service.offering_prayer,
        ),
        ("special_song", weekly.worship.special_song),
        ("sermon_title", weekly.worship.sermon_title),
        ("scripture", weekly.worship.scripture),
        (
            "additional_scripture",
            weekly.worship.additional_scripture,
        ),
        ("decision_hymn", weekly.worship.decision_hymn),
    )

    for name, field in checks:
        if field.status == WeeklyStatus.UNSET:
            missing.append(name)

    return missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    date_value = args.date
    date_token = token(date_value)

    intake = INTAKE_DIR / f"sunday_{date_token}_intake.yaml"
    checklist = INTAKE_DIR / f"sunday_{date_token}_song_checklist.yaml"
    base_weekly = INTAKE_DIR / f"sunday-{date_token}-base.yaml"
    weekly = INTAKE_DIR / f"sunday-{date_token}.yaml"
    bible_requests = INTAKE_DIR / f"sunday_{date_token}_bible_requests.yaml"
    bible = INTAKE_DIR / f"sunday-{date_token}-bible.yaml"
    songs = INTAKE_DIR / f"sunday-{date_token}-songs.yaml"
    song_dir = SONG_ROOT / date_token
    transfer_text = song_dir / "transfer.txt"

    if not intake.exists():
        print(f"STOP: intake가 없습니다: {intake}")
        print("NEXT: python sunday.py paste")
        raise SystemExit(2)

    intake_raw = load(intake)
    if intake_raw.get("review_required"):
        print("STOP: REVIEW 항목을 먼저 처리해야 합니다.")
        for item in intake_raw.get("review_items", []):
            print(f"  - {item}")
        raise SystemExit(3)

    run_script(
        "intake_to_sunday_weekly.py",
        "--intake",
        str(intake),
        "--output",
        str(base_weekly),
    )

    if transfer_text.exists():
        run_script(
            "merge_sunday_transfer.py",
            "--base",
            str(base_weekly),
            "--intake",
            str(intake),
            "--transfer-text",
            str(transfer_text),
            "--output",
            str(weekly),
        )
    else:
        shutil.copyfile(base_weekly, weekly)
        print("\n전달 주보가 아직 없어 주일 안내 데이터만 사용합니다.")
        print(f"expected: {transfer_text}")

    weekly_raw = load(weekly)
    parsed = parse_weekly_data(weekly_raw)
    if not isinstance(parsed, SundayData):
        raise TypeError("생성된 데이터가 SundayData가 아닙니다.")

    missing = operational_missing(parsed)
    if missing:
        print("\nSUNDAY OPERATIONAL DATA: NOT READY")
        print("=" * 60)
        for field in missing:
            print(f"UNSET: {field}")
        print()
        if not transfer_text.exists():
            print(
                "전달 주보가 보완할 수 있는 항목이면 "
                "python sunday.py bulletin <날짜> <전달_주보.hwp> 를 실행하세요."
            )
        print("지난주 값으로 자동 보완하지 않습니다.")
        raise SystemExit(2)

    run_script(
        "build_sunday_bible_requests.py",
        "--weekly",
        str(weekly),
        "--output",
        str(bible_requests),
    )
    run_script("build_bible_library.py")

    bible_code = run_script(
        "resolve_bible_requests.py",
        "--requests",
        str(bible_requests),
        "--output",
        str(bible),
        allow=(0, 2),
    )
    if bible_code == 2:
        raise SystemExit(2)

    if not checklist.exists():
        raise FileNotFoundError(
            f"주일 악보 체크리스트가 없습니다: {checklist}"
        )

    song_code = run_script(
        "refresh_sunday_song_checklist.py",
        "--checklist",
        str(checklist),
        "--song-dir",
        str(song_dir),
        allow=(0, 2),
    )
    if song_code == 2:
        raise SystemExit(2)

    run_script(
        "build_sunday_song_manifest.py",
        "--weekly",
        str(weekly),
        "--checklist",
        str(checklist),
        "--output",
        str(songs),
    )

    print("\n=== SUNDAY READY ===")
    print(f"weekly   : {weekly}")
    print(f"bible    : {bible}")
    print(f"songs    : {songs}")
    print(f"song dir : {song_dir}")
    print(
        "주일 PPT 조립 입력이 준비되었습니다. "
        "다음 단계에서 기존 주일 원본과 연결합니다."
    )


if __name__ == "__main__":
    main()
