from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-09-18"
TOKEN = "20260918"

MEDIA_MAP = {
    "media2.mp4": "opening_song_1.mp4",
    "media3.mp4": "opening_song_2.mp4",
    "media4.mp3": "first_prayer.mp3",
    "media5.mp4": "song_after_prayer.mp4",
    "media6.mp4": "response_song.mp4",
    "media7.mp3": "word_prayer.mp3",
    "media8.mp4": "intercession_song.mp4",
    "media9.mp3": "community_personal_prayer.mp3",
}

CHECKLIST = {
    "items": [
        {
            "field": "opening_song_1",
            "title": "나의 맘 받으소서",
            "media_type": "video",
            "file": None,
        },
        {
            "field": "opening_song_2",
            "title": "아무도 예배하지 않는",
            "media_type": "video",
            "file": None,
        },
        {
            "field": "first_prayer",
            "media_type": "audio",
            "file": None,
        },
        {
            "field": "song_after_prayer",
            "title": "하나님의 은혜",
            "media_type": "video",
            "file": None,
        },
        {
            "field": "response_song",
            "title": "나는 믿네",
            "media_type": "video",
            "file": None,
        },
        {
            "field": "word_prayer",
            "media_type": "audio",
            "file": None,
        },
        {
            "field": "intercession_song",
            "title": "오직 주의 사랑에 매여",
            "media_type": "video",
            "file": None,
        },
        {
            "field": "community_prayer",
            "media_type": "audio",
            "file": None,
        },
        {
            "field": "personal_prayer",
            "media_type": "audio",
            "file": None,
        },
    ]
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "2026-09-18 금요 Zoom 과거 자료를 이용한 Windows 회귀 테스트. "
            "실제 주간 자료 자동 승계 용도가 아닙니다."
        )
    )
    parser.add_argument(
        "--pptx",
        required=True,
        type=Path,
        help="20260918_금요예배(줌).pptx 원본 경로",
    )
    parser.add_argument(
        "--prepare-only",
        action="store_true",
        help="입력 재구성까지만 하고 complete는 실행하지 않습니다.",
    )
    return parser.parse_args()


def run(command: list[str]) -> None:
    print("\n>>>", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def prepare(pptx: Path) -> None:
    pptx = pptx.expanduser().resolve()
    if not pptx.exists():
        raise SystemExit(f"ERROR: PPTX not found: {pptx}")

    media_dir = ROOT / "input" / "friday_zoom" / TOKEN
    intake_dir = ROOT / "output" / "friday_zoom_intake"
    media_dir.mkdir(parents=True, exist_ok=True)
    intake_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="friday0918_") as temp:
        extracted = Path(temp)

        run(
            [
                sys.executable,
                str(ROOT / "scripts" / "inspect_ppt_media.py"),
                str(pptx),
                "--extract-dir",
                str(extracted),
            ]
        )

        for source_name, target_name in MEDIA_MAP.items():
            source = extracted / source_name
            if not source.exists():
                raise SystemExit(
                    f"ERROR: expected valid historical media missing: {source_name}"
                )

            target = media_dir / target_name
            shutil.copy2(source, target)
            print(f"COPIED: {source_name} -> {target.relative_to(ROOT)}")

    # media1.mp3 is intentionally not used: historical file has CRC error.
    weekly_source = ROOT / "samples" / "weekly" / "friday-zoom-20260918.yaml"
    bible_source = (
        ROOT / "samples" / "weekly" / "friday-zoom-20260918-bible.yaml"
    )

    weekly_target = intake_dir / "friday-zoom-20260918.yaml"
    bible_target = intake_dir / "friday-zoom-20260918-bible.yaml"
    checklist_target = (
        intake_dir / "friday_zoom_20260918_media_checklist.yaml"
    )

    shutil.copy2(weekly_source, weekly_target)
    shutil.copy2(bible_source, bible_target)
    checklist_target.write_text(
        yaml.safe_dump(
            CHECKLIST,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print("\n=== 2026-09-18 REGRESSION INPUT READY ===")
    print(f"weekly    : {weekly_target.relative_to(ROOT)}")
    print(f"bible     : {bible_target.relative_to(ROOT)}")
    print(f"checklist : {checklist_target.relative_to(ROOT)}")
    print(f"media     : {media_dir.relative_to(ROOT)}")
    print("note      : media1.mp3(pre-service audio) excluded due to CRC error")


def run_complete() -> int:
    log_path = ROOT / "output" / "friday_0918_windows_complete.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(ROOT / "friday.py"),
        "complete",
        DATE,
    ]

    print("\n>>>", " ".join(command))
    print(f"log: {log_path.relative_to(ROOT)}\n")

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    lines: list[str] = []

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        lines.append(line)

    return_code = process.wait()

    log_path.write_text(
        "".join(lines),
        encoding="utf-8",
    )

    print()
    print("=" * 68)

    if return_code == 0:
        print("FRIDAY 2026-09-18 WINDOWS REGRESSION: PASS")
        print(
            "pptx: output/friday_zoom_20260918_final.pptx"
        )
        print("NEXT: open in PowerPoint and check actual media playback.")
    else:
        print("FRIDAY 2026-09-18 WINDOWS REGRESSION: FAILED")
        print(f"saved log: {log_path.relative_to(ROOT)}")
        print("Keep this log and continue debugging from the exact failure.")

    print("=" * 68)

    return return_code


def main() -> None:
    args = parse_args()
    prepare(args.pptx)

    if args.prepare_only:
        print(
            "\nNEXT: python friday.py complete 2026-09-18"
        )
        return

    raise SystemExit(run_complete())


if __name__ == "__main__":
    main()
