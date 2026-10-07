from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


FIELD_ALIASES = {
    "date": ["날짜", "일자"],
    "opening_song_1": ["찬양1", "시작찬양1", "시작 찬양1"],
    "opening_song_2": ["찬양2", "시작찬양2", "시작 찬양2"],
    "opening_song_3": ["찬양3", "시작찬양3", "시작 찬양3"],
    "separate_hymn": [
        "별도 찬송",
        "별도찬송",
        "찬송",
        "찬송가",
        "예배 찬송",
        "예배찬송",
    ],
    "second_service_prayer": [
        "기도",
        "대표기도",
        "대표 기도",
        "2부 기도",
        "2부기도",
        "2부 대표기도",
        "2부 대표 기도",
    ],
    "church_news": [
        "교회 소식",
        "교회소식",
        "광고",
        "공지",
        "공지사항",
    ],
    "offering_hymn": [
        "봉헌 찬송",
        "봉헌찬송",
        "봉헌 찬양",
        "봉헌찬양",
    ],
    "second_service_offering_prayer": [
        "봉헌 기도",
        "봉헌기도",
        "2부 봉헌 기도",
        "2부 봉헌기도",
    ],
    "special_song": ["특송", "특별찬양", "특별 찬양"],
    "sermon_title": [
        "설교 제목",
        "설교제목",
        "말씀 제목",
        "말씀제목",
        "메시지 제목",
        "제목",
    ],
    "scripture": [
        "본문",
        "성경 본문",
        "성경본문",
        "봉독",
        "성경 봉독",
        "성경봉독",
    ],
    "additional_scripture": [
        "추가 말씀",
        "추가말씀",
        "읽을 말씀",
        "읽을말씀",
        "설교 중 읽을 말씀",
    ],
    "decision_hymn": [
        "결단 찬송",
        "결단찬송",
        "결단 찬양",
        "결단찬양",
        "결단곡",
    ],
}

# 주일 오전 2부 PPT 화면 자체에는 쓰지 않지만 안내에 자주 포함될 수 있는 항목.
# 1부 담당자를 2부 담당자로 오인하지 않도록 명시적으로 무시한다.
IGNORED_ALIASES = {
    "1부 기도",
    "1부기도",
    "1부 대표기도",
    "1부 대표 기도",
    "1부 봉헌 기도",
    "1부 봉헌기도",
    "인도",
    "사회",
    "예배 인도",
    "예배인도",
    "설교자",
    "찬양 담당",
    "찬양담당",
    "찬양 인도",
    "찬양인도",
    "폐회기도",
    "폐회 기도",
}

OPENING_SONG_FIELDS = (
    "opening_song_1",
    "opening_song_2",
    "opening_song_3",
)


def normalize_label(text: str) -> str:
    text = text.lstrip("\ufeff")
    return re.sub(r"\s+", " ", text.strip())


ALIAS_LOOKUP: dict[str, str] = {}
for field, aliases in FIELD_ALIASES.items():
    for alias in aliases:
        ALIAS_LOOKUP[normalize_label(alias)] = field


def empty_record():
    return {
        "status": "missing",
        "value": None,
        "review_required": False,
    }


def asset_required_record(*, source: str, leader: str | None = None):
    record = {
        "status": "asset_required",
        "value": None,
        "review_required": False,
        "source": source,
    }
    if leader:
        record["leader"] = leader
    return record


def normalize_date(value):
    if not value:
        return None

    value = str(value).strip()
    match = re.search(
        r"(\d{4})[.\-/년 ]+(\d{1,2})[.\-/월 ]+(\d{1,2})",
        value,
    )
    if not match:
        return value

    year, month, day = map(int, match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def split_label(line: str):
    line = line.lstrip("\ufeff").strip()
    if not line:
        return None

    normalized = normalize_label(line)

    # 실제 안내에서 '기도(홍길동)'처럼 담당자를 괄호로 붙일 수 있다.
    prayer_match = re.fullmatch(
        r"(?:(?:2부\s*)?(?:기도|대표\s*기도))\s*\(([^)]+)\)",
        normalized,
    )
    if prayer_match:
        return (
            "field",
            "second_service_prayer",
            prayer_match.group(1).strip(),
        )

    offering_prayer_match = re.fullmatch(
        r"(?:(?:2부\s*)?봉헌\s*기도)\s*\(([^)]+)\)",
        normalized,
    )
    if offering_prayer_match:
        return (
            "field",
            "second_service_offering_prayer",
            offering_prayer_match.group(1).strip(),
        )

    # '찬양3(인도자)', '찬양 3곡(인도자)'는 곡명이 아니라
    # 시작 찬양의 곡 수와 인도자 메타데이터로 본다.
    song_count_match = re.fullmatch(
        r"찬양\s*(\d+)\s*(?:곡)?\s*(?:\(([^)]+)\))?",
        normalized,
    )
    if song_count_match:
        return (
            "song_count",
            int(song_count_match.group(1)),
            (song_count_match.group(2) or "").strip(),
        )

    match = re.match(r"^\s*([^:?/]+?)\s*[:?/]\s*(.*)$", line)
    if match:
        raw_label = normalize_label(match.group(1))
        value = match.group(2).strip()
        field = ALIAS_LOOKUP.get(raw_label)
        if field:
            return ("field", field, value)
        if raw_label in IGNORED_ALIASES:
            return ("ignored", raw_label, value)

    field = ALIAS_LOOKUP.get(normalized)
    if field:
        return ("field", field, "")
    if normalized in IGNORED_ALIASES:
        return ("ignored", normalized, "")

    aliases = sorted(
        ALIAS_LOOKUP.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )
    for alias, field in aliases:
        prefix = alias + " "
        if normalized.startswith(prefix):
            value = normalized[len(prefix):].strip()
            if value:
                return ("field", field, value)

    for alias in sorted(IGNORED_ALIASES, key=len, reverse=True):
        prefix = alias + " "
        if normalized.startswith(prefix):
            return (
                "ignored",
                alias,
                normalized[len(prefix):].strip(),
            )

    return None


def _apply_opening_song_count(
    result,
    count: int,
    *,
    source: str,
    leader: str | None,
):
    if count < 0 or count > len(OPENING_SONG_FIELDS):
        return False

    for index, field in enumerate(OPENING_SONG_FIELDS, start=1):
        current = result[field]

        # 명시된 곡 제목은 메타데이터로 덮어쓰지 않는다.
        if current["status"] == "provided":
            continue

        if index <= count:
            result[field] = asset_required_record(
                source=source,
                leader=leader or None,
            )
        else:
            result[field] = {
                "status": "blank",
                "value": None,
                "review_required": False,
            }

    return True


def parse_notice(text: str):
    result = {field: empty_record() for field in FIELD_ALIASES}
    unknown_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        parsed = split_label(line)
        if parsed is None:
            unknown_lines.append(line)
            continue

        kind, name, value = parsed

        if kind == "ignored":
            continue

        if kind == "song_count":
            if not _apply_opening_song_count(
                result,
                int(name),
                source=line,
                leader=str(value or "").strip() or None,
            ):
                unknown_lines.append(line)
            continue

        result[name] = {
            "status": "provided" if value else "blank",
            "value": value or None,
            "review_required": False,
        }

    if result["date"]["status"] == "provided":
        result["date"]["value"] = normalize_date(
            result["date"]["value"]
        )

    return result, unknown_lines


def build_bible_requests(data):
    requests = []

    for field in ("scripture", "additional_scripture"):
        record = data[field]
        if record["status"] != "provided" or not record["value"]:
            continue

        requests.append(
            {
                "source": field,
                "reference": record["value"],
                "translation": "개역개정",
                "display_rule": "세례→침례",
            }
        )

    return {"requests": requests}


def build_song_checklist(data):
    slots = [
        ("opening_song_1", "opening_song_1.pptx"),
        ("opening_song_2", "opening_song_2.pptx"),
        ("opening_song_3", "opening_song_3.pptx"),
        ("separate_hymn", "separate_hymn.pptx"),
        ("offering_hymn", "offering_hymn.pptx"),
        ("special_song", "special_song.pptx"),
        ("decision_hymn", "decision_hymn.pptx"),
    ]

    items = []
    for field, filename in slots:
        record = data[field]
        if record["status"] not in {"provided", "asset_required"}:
            continue

        items.append(
            {
                "field": field,
                "title": record.get("value"),
                "expected_filename": filename,
                "file": None,
            }
        )

    return {"items": items}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--output-dir",
        default="output/sunday_intake",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data, unknown_lines = parse_notice(
        input_path.read_text(encoding="utf-8-sig")
    )

    date_value = (
        data["date"]["value"]
        if data["date"]["status"] == "provided"
        else None
    )

    if date_value and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}",
        str(date_value),
    ):
        token = str(date_value).replace("-", "")
    else:
        token = "unknown"

    intake = {
        "service": "sunday",
        "target": "second_service",
        "review_required": bool(unknown_lines),
        "review_items": unknown_lines,
        "date": data["date"],
        "fields": {
            key: value
            for key, value in data.items()
            if key != "date"
        },
    }

    outputs = {
        output_dir / f"sunday_{token}_intake.yaml": intake,
        output_dir / f"sunday_{token}_bible_requests.yaml": (
            build_bible_requests(data)
        ),
        output_dir / f"sunday_{token}_song_checklist.yaml": (
            build_song_checklist(data)
        ),
    }

    for path, payload in outputs.items():
        path.write_text(
            yaml.safe_dump(
                payload,
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    (
        output_dir / f"sunday_{token}_unrecognized.txt"
    ).write_text(
        "\n".join(unknown_lines),
        encoding="utf-8",
    )

    print("\n=== Sunday Intake ===")
    for field, record in data.items():
        print(f"{field:<32} {record['status']}")

    if unknown_lines:
        print(
            f"\nREVIEW REQUIRED: {len(unknown_lines)} item(s)"
        )
        raise SystemExit(3)


if __name__ == "__main__":
    main()
