from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
INTAKE_DIR = ROOT / "output" / "wednesday_intake"
SONG_ROOT = ROOT / "input" / "wednesday"
DEFAULT_SOURCE = ROOT / "sources" / "수요예배.pptx"
BIBLE_MASTER = ROOT / "data" / "private" / "bible_master.yaml"


def run_script(name, *args, allow=(0,)):
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    print("\n>>>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode not in allow:
        raise SystemExit(result.returncode)
    return result.returncode


def token(date):
    return date.replace("-", "").replace(".", "").strip()


def intake_path(date):
    return INTAKE_DIR / f"wednesday_{token(date)}_intake.yaml"


def checklist_path(date):
    return INTAKE_DIR / f"wednesday_{token(date)}_song_checklist.yaml"


def load_yaml(path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def bible_master_summary():
    master = load_yaml(BIBLE_MASTER)
    if not master:
        return None

    books = master.get("books", {})
    if not isinstance(books, dict):
        return None

    chapters = sum(
        len(value)
        for value in books.values()
        if isinstance(value, dict)
    )
    verses = sum(
        len(verse_map)
        for chapter_map in books.values()
        if isinstance(chapter_map, dict)
        for verse_map in chapter_map.values()
        if isinstance(verse_map, dict)
    )
    return {
        "translation": master.get("translation"),
        "validated": master.get("validated") is True,
        "books": len(books),
        "chapters": chapters,
        "verses": verses,
    }


def print_bible_next(date_value):
    if BIBLE_MASTER.exists():
        print(
            f"\n공용 Bible master에 요청 본문이 없거나 현재 지원 범위를 벗어났습니다.\n"
            f"비상 보완이 필요하면: python wednesday.py bible {date_value}"
        )
    else:
        print("\n공용 개역개정 Bible master가 아직 없습니다.")
        print("교회가 보유한 검증본 YAML/JSON을 준비한 뒤:")
        print("  python wednesday.py bible-master-import <파일경로>")


def newest_intake():
    files = sorted(
        INTAKE_DIR.glob("wednesday_*_intake.yaml"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise SystemExit("ERROR: Wednesday intake not generated")
    return files[0]


def parse_notice(notice: Path):
    code = run_script(
        "parse_wednesday_notice.py",
        "--input", str(notice),
        allow=(0, 3),
    )
    intake = newest_intake()
    data = load_yaml(intake)
    date_record = data.get("date", {})
    if date_record.get("status") != "provided":
        raise SystemExit("ERROR: date was not resolved")
    date_value = str(date_record["value"])

    if code == 3 or data.get("review_required"):
        print(f"\nNEXT: python wednesday.py review {date_value}")
        return

    result = run_script(
        "resume_wednesday_week.py",
        "--date", date_value,
        allow=(0, 2),
    )

    if result == 2:
        print_bible_next(date_value)
        return

    print(f"\nNEXT: add score PPT files under {SONG_ROOT / token(date_value)}")
    print(f"      then python wednesday.py complete {date_value}")


def start(args):
    notice = Path(args.notice)
    if not notice.is_absolute():
        notice = ROOT / notice
    if not notice.exists():
        raise SystemExit(f"ERROR: notice not found: {notice}")
    parse_notice(notice)


def paste(args):
    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; Get-Clipboard -Raw",
    ]
    result = subprocess.run(
        command,
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

    notice_dir = ROOT / "input" / "wednesday" / "notices"
    notice_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    notice = notice_dir / f"notice_{timestamp}.txt"
    notice.write_text(content + "\n", encoding="utf-8")

    print("\n=== CLIPBOARD PREVIEW ===")
    lines = content.splitlines()
    for line in lines[:10]:
        print(line)
    if len(lines) > 10:
        print("...")
    print("=========================")

    parse_notice(notice)


def review(args):
    run_script(
        "resolve_wednesday_review.py",
        "--intake", str(intake_path(args.date)),
        "--show",
        allow=(0, 3),
    )


def ignore(args):
    run_script(
        "resolve_wednesday_review.py",
        "--intake", str(intake_path(args.date)),
        "--ignore", args.text,
        allow=(0, 3),
    )


def assign(args):
    run_script(
        "resolve_wednesday_review.py",
        "--intake", str(intake_path(args.date)),
        "--assign", f"{args.field}={args.text}",
        allow=(0, 3),
    )


def resume(args):
    result = run_script(
        "resume_wednesday_week.py",
        "--date", args.date,
        allow=(0, 2),
    )
    if result == 2:
        print_bible_next(args.date)


def bible(args):
    run_script(
        "manage_wednesday_bible.py",
        "scaffold",
        "--date", args.date,
    )


def bible_register(args):
    run_script(
        "manage_wednesday_bible.py",
        "register",
        "--date", args.date,
    )
    run_script("build_bible_library.py")

    print("\n비상 보완 본문이 로컬 라이브러리에 등록되었습니다.")
    print(f"NEXT: python wednesday.py resume {args.date}")


def bible_master_import(args):
    command_args = [args.input]
    if args.replace:
        command_args.append("--replace")
    run_script("import_bible_master.py", *command_args)
    bible_master_status(args)


def bible_master_status(args):
    summary = bible_master_summary()
    print("\n=== Bible Master Status ===")
    if summary is None:
        print("status      : NOT REGISTERED")
        print(f"expected    : {BIBLE_MASTER}")
        print("translation : 개역개정")
        print("NEXT: python wednesday.py bible-master-import <검증본.yaml|json>")
        return

    print("status      : READY" if summary["validated"] else "status      : INVALID")
    print(f"translation : {summary['translation']}")
    print(f"books       : {summary['books']}")
    print(f"chapters    : {summary['chapters']}")
    print(f"verses      : {summary['verses']}")
    print(f"path        : {BIBLE_MASTER}")
    if summary["translation"] != "개역개정" or not summary["validated"]:
        print("WARNING: 검증 완료된 개역개정 마스터가 아니므로 자동 사용하지 않습니다.")
    elif summary["books"] != 66:
        print("WARNING: 66권 전체가 아니므로 일부 본문은 여전히 중단될 수 있습니다.")


def status(args):
    date_value = args.date
    date_token = token(date_value)
    intake = load_yaml(intake_path(date_value))

    print("\n" + "=" * 64)
    print(f"WEDNESDAY STATUS: {date_value}")
    print("=" * 64)

    if not intake:
        print("intake : NOT CREATED")
        print("NEXT: python wednesday.py paste")
        return

    if intake.get("review_required"):
        print("review : REQUIRED")
        for item in intake.get("review_items", []):
            print(f"  - {item}")
        print(f"NEXT: python wednesday.py review {date_value}")
        return

    print("review : COMPLETE")
    weekly = INTAKE_DIR / f"wednesday-{date_token}.yaml"
    bible_path = INTAKE_DIR / f"wednesday-{date_token}-bible.yaml"
    manifest = INTAKE_DIR / f"wednesday-{date_token}-songs.yaml"

    print(f"weekly : {'READY' if weekly.exists() else 'NOT READY'}")
    print(f"bible  : {'READY' if bible_path.exists() else 'NOT READY'}")
    print(f"songs  : {'READY' if manifest.exists() else 'NOT READY'}")

    checklist = load_yaml(checklist_path(date_value))
    items = checklist.get("items", [])
    if items:
        ready = [item for item in items if item.get("file")]
        print(f"score  : {len(ready)}/{len(items)} READY")
        for item in items:
            if not item.get("file"):
                print(f"  MISSING: {item['expected_filename']} ({item.get('title') or 'title from score PPT'})")
        print(f"folder : {SONG_ROOT / date_token}")

    if not bible_path.exists():
        print_bible_next(date_value)
    else:
        print(f"NEXT: python wednesday.py complete {date_value}")


def complete(args):
    date_value = args.date
    date_token = token(date_value)

    run_script("resume_wednesday_week.py", "--date", date_value)

    source = Path(args.source) if args.source else DEFAULT_SOURCE
    if not source.is_absolute():
        source = ROOT / source
    if not source.exists():
        raise SystemExit(
            "ERROR: source Wednesday PPT not found: "
            f"{source}\n"
            "Place the original reference PPT under sources/수요예배.pptx "
            "or pass --source explicitly."
        )

    weekly = INTAKE_DIR / f"wednesday-{date_token}.yaml"
    bible_path = INTAKE_DIR / f"wednesday-{date_token}-bible.yaml"
    songs = INTAKE_DIR / f"wednesday-{date_token}-songs.yaml"
    output = ROOT / "output" / "wednesday" / f"{date_token}_수요예배.pptx"

    run_script(
        "build_wednesday_operational.py",
        "--weekly", str(weekly),
        "--songs", str(songs),
        "--bible", str(bible_path),
        "--source", str(source),
        "--output", str(output),
    )

    print("\nWEDNESDAY COMPLETE")
    print(f"output: {output}")
    print("최종 사용 전 PowerPoint에서 실제 렌더링/악보 잘림을 확인하세요.")


def main():
    parser = argparse.ArgumentParser(description="Wednesday worship weekly workflow")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("start", help="안내 파일로 시작")
    p.add_argument("notice")
    p.set_defaults(func=start)

    p = sub.add_parser("paste", help="Windows clipboard에서 안내 입력")
    p.set_defaults(func=paste)

    p = sub.add_parser("status", help="진행 상태 확인")
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

    p = sub.add_parser("resume", help="REVIEW/Bible 처리 후 재개")
    p.add_argument("date")
    p.set_defaults(func=resume)

    p = sub.add_parser("bible-master-status", help="공용 개역개정 Bible master 상태 확인")
    p.set_defaults(func=bible_master_status)

    p = sub.add_parser("bible-master-import", help="검증된 공용 개역개정 Bible master 등록")
    p.add_argument("input")
    p.add_argument("--replace", action="store_true")
    p.set_defaults(func=bible_master_import)

    p = sub.add_parser("bible", help="비상용: 누락된 이번 주 본문 입력 파일 만들기")
    p.add_argument("date")
    p.set_defaults(func=bible)

    p = sub.add_parser("bible-register", help="비상용: 확인한 이번 주 본문을 검증/등록")
    p.add_argument("date")
    p.set_defaults(func=bible_register)

    p = sub.add_parser("complete", help="최종 수요예배 PPT 제작")
    p.add_argument("date")
    p.add_argument("--source")
    p.set_defaults(func=complete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
