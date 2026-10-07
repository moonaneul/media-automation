from __future__ import annotations

import argparse
import re
import shutil
from datetime import date
from pathlib import Path

import yaml

from media_automation.bulletin.build import (
    build_bulletin_from_files,
)
from media_automation.bulletin.hwp import (
    extract_hwp_text,
)
from media_automation.bulletin.transfer import (
    parse_bulletin_transfer_text,
)


ROOT = Path(__file__).resolve().parent
INPUT_ROOT = ROOT / "input" / "bulletin"
SUNDAY_ROOT = ROOT / "output" / "sunday_intake"
WORK_ROOT = ROOT / "output" / "bulletin_intake"
OUTPUT_ROOT = ROOT / "output" / "bulletin"


def token(value: str) -> str:
    return value.replace("-", "")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(
            f"ERROR: 날짜는 YYYY-MM-DD 형식이어야 합니다: {value}"
        ) from exc


def week_dir(value: str) -> Path:
    return INPUT_ROOT / token(value)


def state_path(value: str) -> Path:
    return week_dir(value) / "state.yaml"


def sunday_path(value: str) -> Path:
    return SUNDAY_ROOT / f"sunday-{token(value)}.yaml"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(
        path.read_text(encoding="utf-8-sig")
    ) or {}


def save_state(value: str, data: dict) -> None:
    path = state_path(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def transfer_path(value: str) -> Path | None:
    directory = week_dir(value)
    if not directory.exists():
        return None

    candidates = sorted(directory.glob("transfer.*"))

    if not candidates:
        return None

    if len(candidates) > 1:
        raise SystemExit(
            "ERROR: 전달 주보 입력이 여러 개 있습니다:\n"
            + "\n".join(f"  - {path}" for path in candidates)
        )

    return candidates[0]


def read_transfer(path: Path) -> str:
    if path.suffix.lower() in {".hwp", ".hwpx"}:
        return extract_hwp_text(path)

    return path.read_text(encoding="utf-8")


def validate_transfer_date(
    expected: date,
    path: Path,
) -> None:
    raw = read_transfer(path)
    parsed = parse_bulletin_transfer_text(
        raw,
        year=expected.year,
    )

    if parsed.date != expected:
        raise SystemExit(
            "ERROR: 입력한 날짜와 전달 주보 날짜가 다릅니다: "
            f"{expected} != {parsed.date}"
        )


def start(args) -> None:
    expected = parse_date(args.date)

    source = Path(args.transfer).expanduser()
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()

    if not source.exists():
        raise SystemExit(
            f"ERROR: 전달 주보 파일을 찾을 수 없습니다: {source}"
        )

    suffix = source.suffix.lower()
    if suffix not in {".hwp", ".hwpx", ".txt"}:
        raise SystemExit(
            "ERROR: 전달 주보는 .hwp / .hwpx / .txt 파일이어야 합니다."
        )

    target_dir = week_dir(args.date)
    target_dir.mkdir(parents=True, exist_ok=True)

    destination = target_dir / f"transfer{suffix}"

    others = [
        path
        for path in target_dir.glob("transfer.*")
        if path != destination
    ]
    if others:
        raise SystemExit(
            "ERROR: 이미 다른 형식의 전달 주보가 있습니다:\n"
            + "\n".join(f"  - {path}" for path in others)
        )

    shutil.copy2(source, destination)

    try:
        validate_transfer_date(
            expected,
            destination,
        )
    except Exception:
        if destination.exists():
            destination.unlink()
        raise

    state = load_yaml(state_path(args.date))

    if not state:
        state = {
            "date": args.date,
            "bulletin_number": None,
        }

    save_state(args.date, state)

    print("\n=== BULLETIN START ===")
    print(f"date     : {args.date}")
    print(f"transfer : {destination}")
    print(
        f"sunday   : "
        f"{'READY' if sunday_path(args.date).exists() else 'NOT READY'}"
    )
    print("number   : 확인 필요")
    print(
        f"\nNEXT: python bulletin.py status {args.date}"
    )


def normalize_number(value: str) -> str:
    result = value.strip()
    result = re.sub(
        r"^(?:No\.?|N0\.?)\s*",
        "",
        result,
        flags=re.IGNORECASE,
    ).strip()

    if not result:
        raise SystemExit("ERROR: 주보 호수를 입력해주세요.")

    return result


def set_number(args) -> None:
    parse_date(args.date)

    path = state_path(args.date)
    if not path.exists():
        raise SystemExit(
            "ERROR: 먼저 start를 실행해주세요.\n"
            f"python bulletin.py start {args.date} <전달_주보.hwp>"
        )

    state = load_yaml(path)
    number = normalize_number(args.number)
    state["bulletin_number"] = number
    save_state(args.date, state)

    print(f"주보 호수 설정: No. {number}")


def status(args) -> None:
    expected = parse_date(args.date)
    transfer = transfer_path(args.date)
    sunday = sunday_path(args.date)
    state = load_yaml(state_path(args.date))

    print("\n" + "=" * 60)
    print(f"BULLETIN STATUS: {args.date}")
    print("=" * 60)

    print(
        "transfer : "
        + ("READY" if transfer is not None else "NOT PROVIDED")
    )
    print(
        "sunday   : "
        + ("READY" if sunday.exists() else "NOT READY")
    )

    number = state.get("bulletin_number")
    if number:
        print(f"number   : READY (No. {number})")
    else:
        print("number   : 확인 필요")
        print(
            f"  NEXT: python bulletin.py number "
            f"{args.date} <호수>"
        )

    date_matches = False

    if transfer is not None:
        try:
            validate_transfer_date(expected, transfer)
            date_matches = True
            print("date     : MATCH")
        except SystemExit as exc:
            print(f"date     : ERROR ({exc})")

    ready = (
        transfer is not None
        and sunday.exists()
        and bool(number)
        and date_matches
    )

    print()
    if ready:
        print("BULLETIN INPUTS READY")
        print(
            f"NEXT: python bulletin.py complete {args.date}"
        )
    else:
        print("BULLETIN INPUTS NOT READY")


def complete(args) -> None:
    expected = parse_date(args.date)

    transfer = transfer_path(args.date)
    if transfer is None:
        raise SystemExit(
            "ERROR: 전달 주보가 없습니다. 먼저 start를 실행해주세요."
        )

    sunday = sunday_path(args.date)
    if not sunday.exists():
        raise SystemExit(
            "ERROR: 같은 주 Sunday YAML이 준비되지 않았습니다: "
            f"{sunday}"
        )

    state = load_yaml(state_path(args.date))
    number = state.get("bulletin_number")

    if not number:
        raise SystemExit(
            "ERROR: 주보 호수가 확인되지 않았습니다.\n"
            "이전 주 호수에서 자동 계산하지 않습니다.\n"
            f"NEXT: python bulletin.py number {args.date} <호수>"
        )

    validate_transfer_date(
        expected,
        transfer,
    )

    raw = load_yaml(sunday)

    raw_date = str(raw.get("date", ""))
    if raw_date != args.date:
        raise SystemExit(
            "ERROR: Sunday YAML 날짜가 다릅니다: "
            f"{raw_date} != {args.date}"
        )

    bulletin = raw.setdefault("bulletin", {})
    bulletin["number"] = {
        "status": "VALUE",
        "value": str(number),
    }

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    derived_sunday = (
        WORK_ROOT
        / f"sunday-{token(args.date)}-bulletin.yaml"
    )

    derived_sunday.write_text(
        yaml.safe_dump(
            raw,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    output = (
        Path(args.output)
        if args.output
        else OUTPUT_ROOT / f"{token(args.date)}_주보.pdf"
    )

    result = build_bulletin_from_files(
        sunday_yaml=derived_sunday,
        transfer_source=transfer,
        output_pdf=output,
    )

    print("\n=== BULLETIN COMPLETE ===")
    print(f"date     : {args.date}")
    print(f"number   : No. {number}")
    print(f"transfer : {transfer}")
    print(f"sunday   : {sunday}")
    print(f"output   : {result.pdf.path}")

    if result.merge.praise_raw.value is not None:
        print(
            "찬양 원문 :",
            result.merge.praise_raw.value,
        )
        print(
            "※ 찬양 역할은 임의 매핑하지 않았습니다."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="주일 주보 운영 workflow"
    )
    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    p = sub.add_parser(
        "start",
        help="전달 주보를 등록하고 주보 작업 시작",
    )
    p.add_argument("date")
    p.add_argument("transfer")
    p.set_defaults(func=start)

    p = sub.add_parser(
        "status",
        help="주보 준비 상태 확인",
    )
    p.add_argument("date")
    p.set_defaults(func=status)

    p = sub.add_parser(
        "number",
        help="명시적으로 전달받은 주보 호수 설정",
    )
    p.add_argument("date")
    p.add_argument("number")
    p.set_defaults(func=set_number)

    p = sub.add_parser(
        "complete",
        help="필수 입력 확인 후 인쇄용 PDF 생성",
    )
    p.add_argument("date")
    p.add_argument(
        "--output",
        help="출력 PDF 경로(생략 시 output/bulletin/날짜_주보.pdf)",
    )
    p.set_defaults(func=complete)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
