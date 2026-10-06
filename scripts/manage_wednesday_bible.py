from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTAKE_DIR = ROOT / "output" / "wednesday_intake"
INPUT_ROOT = ROOT / "input" / "wednesday"
PRIVATE_SOURCE_DIR = ROOT / "data" / "private" / "bible_sources"
LIBRARY_PATH = ROOT / "data" / "bible_library.yaml"


def token(date: str) -> str:
    return date.replace("-", "").replace(".", "").strip()


def normalize_reference(value: str) -> str:
    return (
        str(value)
        .strip()
        .replace("-", "~")
        .replace("～", "~")
    )


def expected_verse_numbers(reference: str) -> list[int]:
    normalized = normalize_reference(reference)
    match = re.fullmatch(
        r".+?\s+(\d+):(\d+)(?:~(\d+))?",
        normalized,
    )
    if not match:
        raise ValueError(
            "현재 자동 등록은 같은 장 안의 본문 범위만 지원합니다: "
            f"{reference}"
        )

    start = int(match.group(2))
    end = int(match.group(3) or start)
    if end < start:
        raise ValueError(f"잘못된 절 범위입니다: {reference}")
    return list(range(start, end + 1))


def load_yaml(path: Path):
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def normalized_library_references(library: dict) -> set[str]:
    passages = library.get("passages", {})
    if not isinstance(passages, dict):
        return set()
    return {
        normalize_reference(reference)
        for reference in passages
    }


def requested_references(date_token: str) -> list[str]:
    path = INTAKE_DIR / f"wednesday_{date_token}_bible_requests.yaml"
    data = load_yaml(path)
    if not data:
        raise SystemExit(f"ERROR: Bible request file not found: {path}")

    result = []
    for item in data.get("requests", []):
        reference = item.get("reference")
        if reference:
            result.append(str(reference).strip())
    return result


def build_template_payload(references: list[str]) -> dict:
    passages = {}
    for reference in references:
        numbers = expected_verse_numbers(reference)
        display_reference = normalize_reference(reference)
        passages[reference] = {
            "reference": display_reference,
            "verses": {number: "" for number in numbers},
        }

    return {
        "translation": "개역개정",
        "instructions": (
            "각 절에 확인한 개역개정 원문을 입력하세요. "
            "원문에 '세례'가 있으면 그대로 입력하고, 화면 생성 단계에서 '침례'로 바꿉니다."
        ),
        "passages": passages,
    }


def scaffold(date: str) -> Path | None:
    date_token = token(date)
    references = requested_references(date_token)

    library = load_yaml(LIBRARY_PATH)
    known = normalized_library_references(library)
    missing = [
        reference
        for reference in references
        if normalize_reference(reference) not in known
    ]

    if not missing:
        print("BIBLE INPUT: 모든 요청 본문이 이미 검증 라이브러리에 있습니다.")
        return None

    path = INPUT_ROOT / date_token / "bible_input.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        print(f"BIBLE INPUT: 기존 입력 파일을 유지합니다: {path}")
        return path

    path.write_text(
        yaml.safe_dump(
            build_template_payload(missing),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print("\n=== Wednesday Bible Input ===")
    for reference in missing:
        print(f"MISSING: {reference}")
    print(f"\nEDIT: {path}")
    print("각 절의 빈 문자열에 확인한 개역개정 본문을 입력하세요.")
    print(f"완료 후: python wednesday.py bible-register {date}")
    return path


def validate_input_payload(payload: dict) -> dict:
    if payload.get("translation") != "개역개정":
        raise ValueError("translation은 반드시 '개역개정'이어야 합니다.")

    passages = payload.get("passages")
    if not isinstance(passages, dict) or not passages:
        raise ValueError("passages가 비어 있습니다.")

    clean_passages = {}
    for reference, passage in passages.items():
        if not isinstance(passage, dict):
            raise ValueError(f"본문 형식이 잘못되었습니다: {reference}")

        expected = expected_verse_numbers(reference)
        verses = passage.get("verses")
        if not isinstance(verses, dict):
            raise ValueError(f"verses가 필요합니다: {reference}")

        normalized_verses = {}
        for number, text in verses.items():
            try:
                verse_number = int(number)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"절 번호가 정수가 아닙니다: {reference} / {number}"
                ) from error

            if not isinstance(text, str) or not text.strip():
                raise ValueError(
                    f"본문이 비어 있습니다: {reference} {verse_number}절"
                )
            normalized_verses[verse_number] = text.strip()

        actual = sorted(normalized_verses)
        if actual != expected:
            raise ValueError(
                f"절 번호가 범위와 일치하지 않습니다: {reference} "
                f"expected={expected}, actual={actual}"
            )

        clean_passages[reference] = {
            "reference": normalize_reference(
                passage.get("reference") or reference
            ),
            "verses": {
                number: normalized_verses[number]
                for number in expected
            },
        }

    return {
        "translation": "개역개정",
        "validated": True,
        "source_note": "user-verified local Bible input",
        "passages": clean_passages,
    }


def register(date: str) -> Path:
    date_token = token(date)
    input_path = INPUT_ROOT / date_token / "bible_input.yaml"
    if not input_path.exists():
        raise SystemExit(
            f"ERROR: Bible input file not found: {input_path}\n"
            f"먼저 python wednesday.py bible {date} 를 실행하세요."
        )

    payload = validate_input_payload(load_yaml(input_path))

    PRIVATE_SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    output = PRIVATE_SOURCE_DIR / f"wednesday-{date_token}.yaml"

    if output.exists():
        existing = load_yaml(output)
        if existing != payload:
            raise SystemExit(
                "ERROR: 같은 날짜의 검증 본문 파일이 이미 있고 내용이 다릅니다. "
                f"자동 덮어쓰지 않습니다: {output}"
            )
        print(f"BIBLE REGISTER: 이미 같은 내용으로 등록됨: {output}")
        return output

    output.write_text(
        yaml.safe_dump(
            payload,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print("\n=== Bible Registered ===")
    for reference in payload["passages"]:
        print(f"OK: {reference}")
    print(f"source: {output}")
    return output


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scaffold")
    p.add_argument("--date", required=True)

    p = sub.add_parser("register")
    p.add_argument("--date", required=True)

    args = parser.parse_args()

    if args.command == "scaffold":
        scaffold(args.date)
    else:
        register(args.date)


if __name__ == "__main__":
    main()
