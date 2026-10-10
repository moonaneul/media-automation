from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from media_automation.bulletin.source import find_transfer


ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
INTAKE_DIR = ROOT / "output" / "sunday_intake"
INPUT_ROOT = ROOT / "input" / "sunday"
BULLETIN_ROOT = ROOT / "input" / "bulletin"


def run_script(name, *args, allow=(0,)):
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    print("\n>>>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode not in allow:
        raise SystemExit(result.returncode)
    return result.returncode


def token(date_value: str) -> str:
    return date_value.replace("-", "").replace(".", "").strip()


def intake_path(date_value: str) -> Path:
    return INTAKE_DIR / f"sunday_{token(date_value)}_intake.yaml"


def checklist_path(date_value: str) -> Path:
    return INTAKE_DIR / f"sunday_{token(date_value)}_song_checklist.yaml"


def weekly_path(date_value: str) -> Path:
    return INTAKE_DIR / f"sunday-{token(date_value)}.yaml"


def bible_path(date_value: str) -> Path:
    return INTAKE_DIR / f"sunday-{token(date_value)}-bible.yaml"


def songs_path(date_value: str) -> Path:
    return INTAKE_DIR / f"sunday-{token(date_value)}-songs.yaml"


def transfer_text_path(date_value: str) -> Path:
    return INPUT_ROOT / token(date_value) / "transfer.txt"


def registered_transfer(date_value: str) -> Path | None:
    return (
        find_transfer(BULLETIN_ROOT / token(date_value))
        or (transfer_text_path(date_value) if transfer_text_path(date_value).is_file() else None)
    )


def load_yaml(path: Path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def clipboard_command() -> list[str]:
    system = platform.system()

    if system == "Darwin":
        return ["pbpaste"]

    if system == "Windows":
        return [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            (
                "[Console]::OutputEncoding="
                "[System.Text.Encoding]::UTF8; "
                "Get-Clipboard -Raw"
            ),
        ]

    raise RuntimeError(
        f"지원하지 않는 clipboard 운영체제입니다: {system}"
    )


def newest_intake() -> Path:
    files = sorted(
        INTAKE_DIR.glob("sunday_*_intake.yaml"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise SystemExit("ERROR: Sunday intake not generated")
    return files[0]


def parse_notice(notice: Path):
    code = run_script(
        "parse_sunday_notice.py",
        "--input",
        str(notice),
        allow=(0, 3),
    )

    intake = newest_intake()
    data = load_yaml(intake)
    date_record = data.get("date", {})

    if date_record.get("status") != "provided":
        raise SystemExit("ERROR: date was not resolved")

    date_value = str(date_record["value"])

    if code == 3 or data.get("review_required"):
        print(f"\nNEXT: python sunday.py review {date_value}")
        return

    result = run_script(
        "resume_sunday_week.py",
        "--date",
        date_value,
        allow=(0, 2),
    )

    if result == 2:
        print(f"\nNEXT: python sunday.py status {date_value}")
        return

    print(f"\nSUNDAY INPUT READY: {date_value}")
    print("다음 단계에서 기존 주일예배 PPT 원본과 연결합니다.")


def start(args):
    notice = Path(args.notice).expanduser()
    if not notice.is_absolute():
        notice = ROOT / notice
    if not notice.exists():
        raise SystemExit(f"ERROR: notice not found: {notice}")
    parse_notice(notice)


def paste(args):
    result = subprocess.run(
        clipboard_command(),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit("ERROR: clipboard could not be read")

    content = result.stdout.strip()
    if not content:
        raise SystemExit("ERROR: clipboard is empty")

    notice_dir = INPUT_ROOT / "notices"
    notice_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    notice = notice_dir / f"notice_{timestamp}.txt"
    notice.write_text(content + "\n", encoding="utf-8")

    print("\n=== CLIPBOARD PREVIEW ===")
    lines = content.splitlines()
    for line in lines[:12]:
        print(line)
    if len(lines) > 12:
        print("...")
    print("=========================")

    parse_notice(notice)


def bulletin(args):
    source = Path(args.file).expanduser()
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()
    command = [sys.executable, str(ROOT / "bulletin.py"), "start", args.date, str(source)]
    if args.replace:
        command.append("--replace")
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)

    result = run_script(
        "resume_sunday_week.py",
        "--date",
        args.date,
        allow=(0, 2),
    )

    if result == 2:
        print(f"\nNEXT: python sunday.py status {args.date}")


def resume(args):
    result = run_script(
        "resume_sunday_week.py",
        "--date",
        args.date,
        allow=(0, 2, 3),
    )

    if result in {2, 3}:
        print(f"\nNEXT: python sunday.py status {args.date}")


def song_register(args):
    command_args = [args.date, args.slot, args.file]
    if args.replace:
        command_args.append("--replace")
    run_script("register_sunday_song.py", *command_args)


def review(args):
    run_script(
        "resolve_sunday_review.py",
        "--intake",
        str(intake_path(args.date)),
        "--show",
        allow=(0, 3),
    )


def ignore(args):
    run_script(
        "resolve_sunday_review.py",
        "--intake",
        str(intake_path(args.date)),
        "--ignore",
        args.text,
        allow=(0, 3),
    )


def assign(args):
    run_script(
        "resolve_sunday_review.py",
        "--intake",
        str(intake_path(args.date)),
        "--assign",
        f"{args.field}={args.text}",
        allow=(0, 3),
    )


def _resolved_source(value: str) -> Path:
    source = Path(value).expanduser()
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()
    if not source.exists():
        raise SystemExit(f"ERROR: 주일 원본 PPT를 찾을 수 없습니다: {source}")
    return source


def structure(args):
    source = _resolved_source(args.source)
    run_script(
        "complete_sunday_week.py",
        "--date",
        args.date,
        "--source",
        str(source),
        "--structure-only",
    )


def complete(args):
    source = _resolved_source(args.source)
    run_script(
        "complete_sunday_week.py",
        "--date",
        args.date,
        "--source",
        str(source),
    )


def status(args):
    date_value = args.date
    date_token = token(date_value)
    intake = load_yaml(intake_path(date_value))

    print("\n" + "=" * 64)
    print(f"SUNDAY STATUS: {date_value}")
    print("=" * 64)

    if not intake:
        print("intake   : NOT CREATED")
        print("NEXT: python sunday.py paste")
        return

    if intake.get("review_required"):
        print("review   : REQUIRED")
        for item in intake.get("review_items", []):
            print(f"  - {item}")
        print(f"NEXT: python sunday.py review {date_value}")
        return

    print("review   : COMPLETE")
    print(
        f"bulletin : "
        f"{'READY' if registered_transfer(date_value) else 'NOT PROVIDED'}"
    )
    print(f"weekly   : {'READY' if weekly_path(date_value).exists() else 'NOT READY'}")
    print(f"bible    : {'READY' if bible_path(date_value).exists() else 'NOT READY'}")
    checklist = load_yaml(checklist_path(date_value))
    items = checklist.get("items", [])
    song_dir = INPUT_ROOT / date_token
    scores_ready = checklist_path(date_value).is_file() and all(
        item.get("expected_filename")
        and (song_dir / item["expected_filename"]).is_file()
        for item in items
    )
    print(
        f"songs    : "
        f"{'READY' if songs_path(date_value).exists() and scores_ready else 'NOT READY'}"
    )

    weekly = load_yaml(weekly_path(date_value))
    if weekly:
        unset = []
        worship = weekly.get("worship", {})
        serving = weekly.get("serving", {})
        bulletin_data = weekly.get("bulletin", {})

        def check(name, value):
            if isinstance(value, dict) and value.get("status") == "UNSET":
                unset.append(name)

        for index, value in enumerate(worship.get("opening_songs", []), start=1):
            check(f"opening_song_{index}", value)
        check("separate_hymn", worship.get("separate_hymn", {}))
        check("offering_hymn", worship.get("offering_hymn", {}))
        check("special_song", worship.get("special_song", {}))
        check("sermon_title", worship.get("sermon_title", {}))
        check("scripture", worship.get("scripture", {}))
        check("additional_scripture", worship.get("additional_scripture", {}))
        check("decision_hymn", worship.get("decision_hymn", {}))

        this_week = serving.get("this_week", {})
        second = this_week.get("second_service", {})
        check("second_service_prayer", second.get("prayer", {}))
        check(
            "second_service_offering_prayer",
            second.get("offering_prayer", {}),
        )
        check("church_news", bulletin_data.get("church_news", {}))

        if unset:
            print("operational: NOT READY")
            for field in unset:
                print(f"  UNSET: {field}")

    if items:
        ready_count = 0
        for item in items:
            expected = item.get("expected_filename")
            candidate = song_dir / expected if expected else None
            ready = bool(candidate and candidate.is_file())
            if ready:
                ready_count += 1
            else:
                print(
                    f"  MISSING SCORE: {expected} "
                    f"({item.get('title') or 'title from score PPT'})"
                )
        print(f"score    : {ready_count}/{len(items)} READY")
        print(f"folder   : {song_dir}")
        if ready_count < len(items):
            print(
                "NEXT: python sunday.py song-register "
                f"{date_value} <슬롯> <악보.ppt|pptx>"
            )

    transfer = registered_transfer(date_value)
    if transfer is not None:
        print(f"transfer : {transfer}")

    if (
        weekly_path(date_value).exists()
        and bible_path(date_value).exists()
        and songs_path(date_value).exists()
        and scores_ready
    ):
        print("\nSUNDAY INPUTS READY")
        print(
            "NEXT (구조 검증): python sunday.py structure "
            f"{date_value} <주일원본.pptx>"
        )
        print(
            "NEXT (최종 제작): python sunday.py complete "
            f"{date_value} <주일원본.pptx>"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Sunday second-service weekly workflow"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="주일예배 안내 파일로 시작")
    p.add_argument("notice")
    p.set_defaults(func=start)

    p = sub.add_parser("paste", help="clipboard에서 주일예배 안내 입력")
    p.set_defaults(func=paste)

    p = sub.add_parser("bulletin", help="같은 주 전달 주보 HWP/TXT 등록")
    p.add_argument("date")
    p.add_argument("file")
    p.add_argument("--replace", action="store_true", help="등록된 전달 주보 수정본으로 교체")
    p.set_defaults(func=bulletin)

    p = sub.add_parser("resume", help="입력 보완 후 주일 파이프라인 재개")
    p.add_argument("date")
    p.set_defaults(func=resume)

    p = sub.add_parser("song-register", help="악보 PPT를 이번 주 찬양 슬롯에 등록")
    p.add_argument("date")
    p.add_argument("slot", help="1, 2, 3, separate, offering, special, decision")
    p.add_argument("file")
    p.add_argument("--replace", action="store_true", help="기존 슬롯 파일 교체")
    p.set_defaults(func=song_register)

    p = sub.add_parser("status", help="주일예배 준비 상태 확인")
    p.add_argument("date")
    p.set_defaults(func=status)

    p = sub.add_parser("review", help="REVIEW 문장 보기")
    p.add_argument("date")
    p.set_defaults(func=review)

    p = sub.add_parser("ignore", help="REVIEW 문장 무시")
    p.add_argument("date")
    p.add_argument("text")
    p.set_defaults(func=ignore)

    p = sub.add_parser("assign", help="REVIEW 문장을 필드에 배정")
    p.add_argument("date")
    p.add_argument("field")
    p.add_argument("text")
    p.set_defaults(func=assign)

    p = sub.add_parser(
        "structure",
        help="Mac에서도 가능한 주일 PPT 구조 프리뷰 + QA",
    )
    p.add_argument("date")
    p.add_argument("source", help="과거 주일 오전 2부 원본 PPT")
    p.set_defaults(func=structure)

    p = sub.add_parser(
        "complete",
        help="원본 악보를 병합한 주일 PPT 생성 (Windows/macOS/Linux)",
    )
    p.add_argument("date")
    p.add_argument("source", help="과거 주일 오전 2부 원본 PPT")
    p.set_defaults(func=complete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
