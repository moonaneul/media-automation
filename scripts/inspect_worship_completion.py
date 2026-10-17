"""Read-only diagnosis of a Sunday's completion and archive state.

Never writes to the work database, generated files, or OneDrive.
Prints only field *names* and states, not private field contents or OAuth data.
"""
import argparse
import json
import re
import sqlite3
from pathlib import Path


def inspect(database: Path, day: str, service: str = "sunday") -> int:
    if not database.is_file():
        print("ERROR: 작업 DB 파일이 없습니다. 경로 확인이 필요합니다.")
        return 2
    try:
        with sqlite3.connect(f"file:{database.resolve().as_posix()}?mode=ro", uri=True) as db:
            row = db.execute(
                "SELECT revision,payload FROM works WHERE date=? AND service=?",
                (day, service),
            ).fetchone()
            if row is None:
                print(f"ERROR: {day} {service}의 저장된 예배 입력을 찾지 못했습니다.")
                return 2
            revision, payload = row
            record = json.loads(payload)
            settings_row = db.execute(
                "SELECT payload FROM bulletin_settings WHERE id=1"
            ).fetchone() if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bulletin_settings'"
            ).fetchone() else None
        print(f"대상: {day} {service} / 저장 revision: {revision}")
        print("내용 값과 개인정보는 출력하지 않습니다.")
        if settings_row:
            settings = json.loads(settings_row[0])
            print(f"교회 고정 설정 확인 상태: {settings.get('status', '(없음)')}")
        outputs = record.get("outputs") or {}
        files = database.with_suffix(".generated")
        for kind in ("ppt", "pdf"):
            data = outputs.get(kind) or {}
            identifier = data.get("fileId", "")
            print(f"\n[{kind.upper()}]")
            print(f"  생성={bool(data.get('generated'))}, 검수완료={bool(data.get('complete'))}, "
                  f"입력변경={bool(data.get('changed'))}, OneDrive기록={data.get('archiveStatus', '(없음)')}")
            missing = data.get("unresolved") or []
            print(f"  웹 화면 확인 필요 {len(missing)}건: {', '.join(map(str, missing)) if missing else '(없음)'}")
            if not re.fullmatch(r"[0-9a-f]{32}", identifier):
                print("  생성 결과 ID 미등록")
                continue
            pdf_path = files / (identifier + (".pdf" if kind == "pdf" else ".pptx"))
            report_path = files / (identifier + ".json")
            print(f"  실제 생성 파일 존재={pdf_path.is_file()}, 제작 리포트 존재={report_path.is_file()}")
            if not report_path.is_file():
                continue
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report_missing = report.get("unresolved") or []
            print(f"  생성 리포트 확인 필요 {len(report_missing)}건: "
                  f"{', '.join(map(str, report_missing)) if report_missing else '(없음)'}")
            if kind == "pdf":
                changed_fields = report.get("fields") != record.get("fields")
                print(f"  생성 이후 입력 상태 불일치={changed_fields}")
                if settings_row:
                    print(f"  생성 이후 교회 고정 설정 변경됨={report.get('settings') != settings}")
                print("  리포트의 필수 확인 항목별 현재 입력 상태:")
                for label in report_missing:
                    field = record.get("fields", {}).get(label)
                    state = field.get("state", "UNSET") if isinstance(field, dict) else "(일반 입력 칸 아님)"
                    print(f"    - {label}: {state}")
        return 0
    except (sqlite3.Error, ValueError, OSError, KeyError, TypeError) as exc:
        print(f"ERROR: 작업 상태를 읽지 못했습니다. ({type(exc).__name__})")
        return 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--date", default="2026-10-18")
    parser.add_argument("--service", choices=("sunday", "wednesday", "friday"), default="sunday")
    args = parser.parse_args()
    raise SystemExit(inspect(args.database, args.date, args.service))


if __name__ == "__main__":
    main()
