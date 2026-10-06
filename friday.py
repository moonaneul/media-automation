from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
INTAKE_DIR = ROOT / "output" / "friday_zoom_intake"
MEDIA_ROOT = ROOT / "input" / "friday_zoom"


def run_script(name, *args, allow=(0,)):
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    print()
    print(">>>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode not in allow:
        raise SystemExit(result.returncode)
    return result.returncode


def token(date):
    return date.replace("-", "").replace(".", "").strip()


def intake_path(date):
    return INTAKE_DIR / f"friday_zoom_{token(date)}_intake.yaml"


def checklist_path(date):
    return INTAKE_DIR / f"friday_zoom_{token(date)}_media_checklist.yaml"


def load_yaml(path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def start(args):
    notice = Path(args.notice)
    if not notice.is_absolute():
        notice = ROOT / notice
    if not notice.exists():
        raise SystemExit(f"ERROR: notice not found: {notice}")
    run_script(
        "start_friday_zoom_week.py",
        "--notice", str(notice),
        allow=(0, 2, 3),
    )


def paste(args):
    from datetime import datetime

    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        (
            "[Console]::OutputEncoding="
            "[System.Text.Encoding]::UTF8; "
            "Get-Clipboard -Raw"
        ),
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    if result.returncode != 0:
        raise SystemExit(
            "ERROR: clipboard could not be read."
        )

    content = result.stdout.strip()

    if not content:
        raise SystemExit(
            "ERROR: clipboard is empty."
        )

    print()
    print("=== CLIPBOARD PREVIEW ===")

    lines = content.splitlines()

    for line in lines[:8]:
        print(line)

    if len(lines) > 8:
        print("...")

    print("=========================")
    print()

    notice_dir = (
        ROOT
        / "input"
        / "friday_zoom"
        / "notices"
    )

    notice_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    notice = (
        notice_dir
        / f"notice_{timestamp}.txt"
    )

    notice.write_text(
        content + "\n",
        encoding="utf-8",
    )

    print(
        f"NOTICE SAVED: {notice}"
    )

    run_script(
        "start_friday_zoom_week.py",
        "--notice",
        str(notice),
        allow=(0, 2, 3),
    )


def review(args):
    run_script(
        "resolve_friday_zoom_review.py",
        "--intake", str(intake_path(args.date)),
        "--show",
        allow=(0, 3),
    )


def ignore(args):
    run_script(
        "resolve_friday_zoom_review.py",
        "--intake", str(intake_path(args.date)),
        "--ignore", args.text,
        allow=(0, 3),
    )


def assign(args):
    run_script(
        "resolve_friday_zoom_review.py",
        "--intake", str(intake_path(args.date)),
        "--assign", f"{args.field}={args.text}",
        allow=(0, 3),
    )


def resume(args):
    run_script(
        "resume_friday_zoom_week.py",
        "--date", args.date,
    )


def complete(args):
    run_script(
        "complete_friday_zoom_week.py",
        "--date", args.date,
    )


def status(args):
    date = args.date
    date_token = token(date)
    intake = load_yaml(intake_path(date))

    print()
    print("=" * 64)
    print(f"FRIDAY ZOOM STATUS: {date}")
    print("=" * 64)

    if not intake:
        print("intake : NOT CREATED")
        print()
        print("NEXT: python friday.py start <notice-file>")
        return

    if intake.get("review_required", False):
        print("review : REQUIRED")
        for item in intake.get("review_items", []):
            print(f"  - {item}")
        print()
        print(f"NEXT: python friday.py review {date}")
        return

    print("review : COMPLETE")

    weekly = INTAKE_DIR / f"friday-zoom-{date_token}.yaml"
    bible = INTAKE_DIR / f"friday-zoom-{date_token}-bible.yaml"

    print(f"weekly : {'READY' if weekly.exists() else 'NOT READY'}")
    print(f"bible  : {'READY' if bible.exists() else 'NOT READY'}")

    checklist = load_yaml(checklist_path(date))
    items = checklist.get("items", [])

    if not items:
        print("media  : CHECKLIST NOT READY")
        print()
        print(f"NEXT: python friday.py resume {date}")
        return

    missing = [item for item in items if not item.get("file")]

    print(f"media  : {len(items) - len(missing)}/{len(items)} READY")

    if missing:
        for item in missing:
            field = item.get("field", "?")
            title = item.get("title")
            if title:
                print(f"  MISSING: {field} ({title})")
            else:
                print(f"  MISSING: {field}")

        print()
        print(f"folder : {MEDIA_ROOT / date_token}")
        print(f"NEXT: add media, then python friday.py complete {date}")
        return

    print()
    print(f"NEXT: python friday.py complete {date}")


def main():
    parser = argparse.ArgumentParser(
        description="Friday Zoom weekly workflow"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="이번 주 안내 입력")
    p.add_argument("notice")
    p.set_defaults(func=start)

    p = sub.add_parser(
        "paste",
        help="Start from Windows clipboard",
    )
    p.set_defaults(func=paste)

    p = sub.add_parser("status", help="현재 진행 상태 확인")
    p.add_argument("date")
    p.set_defaults(func=status)

    p = sub.add_parser("review", help="확인이 필요한 문장 보기")
    p.add_argument("date")
    p.set_defaults(func=review)

    p = sub.add_parser("ignore", help="REVIEW 문장 무시 처리")
    p.add_argument("date")
    p.add_argument("text")
    p.set_defaults(func=ignore)

    p = sub.add_parser("assign", help="REVIEW 문장을 특정 항목에 배정")
    p.add_argument("date")
    p.add_argument("field")
    p.add_argument("text")
    p.set_defaults(func=assign)

    p = sub.add_parser("resume", help="REVIEW 처리 후 재개")
    p.add_argument("date")
    p.set_defaults(func=resume)

    p = sub.add_parser("complete", help="최종 PPT 제작")
    p.add_argument("date")
    p.set_defaults(func=complete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
