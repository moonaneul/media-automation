from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


FIELD_ALIASES = {
    "date": [
        "날짜",
        "일자",
    ],
    "opening_song_1": [
        "찬양1",
        "시작찬양1",
        "시작 찬양1",
    ],
    "opening_song_2": [
        "찬양2",
        "시작찬양2",
        "시작 찬양2",
    ],
    "first_prayer": [
        "첫 기도",
        "첫기도",
        "기도1",
        "첫 기도 제목",
        "기도 제목",
        "기도제목",
    ],
    "song_after_prayer": [
        "찬양3",
        "기도 후 찬양",
        "기도후 찬양",
    ],
    "scripture": [
        "본문",
        "성경 본문",
        "성경본문",
        "봉독",
        "말씀",
        "성경",
    ],
    "sermon_title": [
        "설교 제목",
        "설교제목",
        "메시지 제목",
        "말씀 제목",
        "제목",
    ],
    "additional_scripture": [
        "추가 말씀",
        "추가말씀",
        "읽을 말씀",
        "읽을말씀",
    ],
    "response_song": [
        "응답 찬양",
        "응답찬양",
        "응답곡",
        "결단 찬양",
        "결단찬양",
    ],
    "word_prayer": [
        "말씀 기도",
        "말씀기도",
        "말씀 관련 기도",
        "말씀관련기도",
    ],
    "intercession_song": [
        "중보 찬양",
        "중보찬양",
        "공동체 찬양",
    ],
    "community_prayer": [
        "공동체 기도",
        "공동체기도",
        "공동체·중보기도",
        "공동체 중보기도",
        "공동체/중보기도",
        "중보 기도",
        "중보기도",
    ],
    "personal_prayer": [
        "개인 기도",
        "개인기도",
    ],
}


MULTILINE_FIELDS = {
    "first_prayer",
    "word_prayer",
    "community_prayer",
    "personal_prayer",
}


def normalize_label(text: str) -> str:
    # Strip a UTF-8 BOM that may be added by Windows PowerShell.
    text = text.lstrip("\ufeff")

    return re.sub(
        r"\s+",
        " ",
        text.strip(),
    )


ALIAS_LOOKUP = {}

for field, aliases in FIELD_ALIASES.items():
    for alias in aliases:
        ALIAS_LOOKUP[
            normalize_label(alias)
        ] = field


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        required=True,
    )

    parser.add_argument(
        "--output-dir",
        default="output/friday_zoom_intake",
    )

    return parser.parse_args()


def strip_bullet(line: str) -> str:
    return re.sub(
        r"^\s*(?:[-*•·]|\d+[.)])\s*",
        "",
        line,
    ).strip()


def split_label(line: str):
    line = line.lstrip("\ufeff").strip()

    if not line:
        return None

    # 1. Explicit separators:
    # label: value
    # label?value
    # label / value
    match = re.match(
        r"^\s*([^:?/]+?)\s*[:?/]\s*(.*)$",
        line,
    )

    if match:
        raw_label = normalize_label(
            match.group(1)
        )

        field = ALIAS_LOOKUP.get(
            raw_label
        )

        if field:
            return (
                field,
                match.group(2).strip(),
            )

    normalized = normalize_label(
        line
    )

    # 2. Exact label with no value.
    field = ALIAS_LOOKUP.get(
        normalized
    )

    if field:
        return (
            field,
            "",
        )

    # 3. Common chat style:
    # "?? ?? 9:1~10"
    # Common chat-style label followed by a value.
    #
    # Only accept a prefix when it exactly matches
    # one of the known aliases.
    aliases = sorted(
        ALIAS_LOOKUP.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for alias, field in aliases:
        prefix = alias + " "

        if normalized.startswith(
            prefix
        ):
            value = normalized[
                len(prefix):
            ].strip()

            if value:
                return (
                    field,
                    value,
                )

    return None



def empty_record():
    return {
        "status": "missing",
        "value": None,
        "review_required": False,
    }


def parse_notice(text: str):
    result = {
        field: empty_record()
        for field in FIELD_ALIASES
    }

    unknown_lines = []
    current_field = None

    lines = text.splitlines()

    def parse_list_item(value: str):
        value = value.strip()

        # Bullet only:
        # - text
        # * text
        # ? text
        match = re.match(
            r"^(?:[-*\u2022\u00b7])\s*(.+)$",
            value,
        )

        if match:
            return match.group(1).strip()

        # Numbered forms:
        # 1. text
        # 1) text
        # 1 - text
        # 1. - text
        # (1) - text
        # ? - text
        match = re.match(
            r"^(?:"
            r"\d+\s*[.)]?"
            r"|\(\d+\)"
            r"|[\u2460-\u2473]"
            r")"
            r"\s*"
            r"(?:[-*\u2022\u00b7]\s*)?"
            r"(.+)$",
            value,
        )

        if match:
            return match.group(1).strip()

        return None

    for raw_line in lines:
        line = raw_line.rstrip()

        # Blank line ends a multiline section.
        if not line.strip():
            current_field = None
            continue

        label_result = split_label(
            line
        )

        if label_result:
            field, value = label_result

            current_field = (
                field
                if field in MULTILINE_FIELDS
                else None
            )

            if value:
                result[field] = {
                    "status": "provided",
                    "value": value,
                    "review_required": False,
                }
            else:
                result[field] = {
                    "status": "blank",
                    "value": (
                        []
                        if field in MULTILINE_FIELDS
                        else None
                    ),
                    "review_required": False,
                }

            continue

        stripped = line.strip()

        # A multiline field accepts only an explicit
        # bullet/numbered list item.
        if (
            current_field
            and current_field in MULTILINE_FIELDS
        ):
            item = parse_list_item(
                stripped
            )

            if item is not None:
                if not item:
                    continue

                record = result[
                    current_field
                ]

                if record["status"] == "blank":
                    record["status"] = "provided"
                    record["value"] = []

                if not isinstance(
                    record["value"],
                    list,
                ):
                    previous = record[
                        "value"
                    ]

                    record["value"] = (
                        [previous]
                        if previous
                        else []
                    )

                record["value"].append(
                    item
                )

                continue

        # Never guess an ordinary sentence as
        # part of a prayer/topic list.
        unknown_lines.append(
            stripped
        )

        current_field = None

    return result, unknown_lines




def normalize_date(value):
    if not value:
        return None

    value = str(value).strip()

    match = re.search(
        r"(\d{4})[.\-/년 ]+"
        r"(\d{1,2})[.\-/월 ]+"
        r"(\d{1,2})",
        value,
    )

    if not match:
        return value

    year, month, day = (
        int(match.group(1)),
        int(match.group(2)),
        int(match.group(3)),
    )

    return (
        f"{year:04d}-"
        f"{month:02d}-"
        f"{day:02d}"
    )


def build_bible_requests(data):
    requests = []

    for key in (
        "scripture",
        "additional_scripture",
    ):
        record = data[key]

        if record["status"] != "provided":
            continue

        value = record["value"]

        if not value:
            continue

        requests.append(
            {
                "source": key,
                "reference": value,
                "translation": "개역개정",
                "display_rule": "세례→침례",
            }
        )

    return {
        "requests": requests,
    }


def build_media_checklist(data):
    items = []

    song_fields = [
        (
            "opening_song_1",
            "video",
        ),
        (
            "opening_song_2",
            "video",
        ),
        (
            "song_after_prayer",
            "video",
        ),
        (
            "response_song",
            "video",
        ),
        (
            "intercession_song",
            "video",
        ),
    ]

    for field, media_type in song_fields:
        record = data[field]

        if record["status"] != "provided":
            continue

        if not record["value"]:
            continue

        items.append(
            {
                "field": field,
                "title": record["value"],
                "media_type": media_type,
                "file": None,
                "permission_confirmed": False,
            }
        )

    prayer_fields = [
        "first_prayer",
        "word_prayer",
        "community_prayer",
        "personal_prayer",
    ]

    for field in prayer_fields:
        record = data[field]

        if record["status"] == "provided":
            items.append(
                {
                    "field": field,
                    "media_type": "audio",
                    "file": None,
                }
            )

    return {
        "items": items,
    }


def main():
    args = parse_args()

    input_path = Path(
        args.input
    )

    output_dir = Path(
        args.output_dir
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    text = input_path.read_text(
        encoding="utf-8-sig",
    )

    data, unknown_lines = (
        parse_notice(text)
    )

    if (
        data["date"]["status"]
        == "provided"
    ):
        data["date"]["value"] = (
            normalize_date(
                data["date"]["value"]
            )
        )

    date_value = (
        data["date"]["value"]
        if data["date"]["status"]
        == "provided"
        else None
    )

    if (
        date_value
        and re.fullmatch(
            r"\d{4}-\d{2}-\d{2}",
            str(date_value),
        )
    ):
        date_token = str(
            date_value
        ).replace(
            "-",
            "",
        )
    else:
        date_token = "unknown"

    intake = {
        "service": "friday_zoom",
        "review_required": bool(
            unknown_lines
        ),
        "review_items": list(
            unknown_lines
        ),
        "date": data["date"],
        "fields": {
            key: value
            for key, value in data.items()
            if key != "date"
        },
    }

    intake_path = (
        output_dir
        / f"friday_zoom_{date_token}_intake.yaml"
    )

    bible_path = (
        output_dir
        / f"friday_zoom_{date_token}_bible_requests.yaml"
    )

    media_path = (
        output_dir
        / f"friday_zoom_{date_token}_media_checklist.yaml"
    )

    unknown_path = (
        output_dir
        / f"friday_zoom_{date_token}_unrecognized.txt"
    )

    intake_path.write_text(
        yaml.safe_dump(
            intake,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    bible_path.write_text(
        yaml.safe_dump(
            build_bible_requests(
                data
            ),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    media_path.write_text(
        yaml.safe_dump(
            build_media_checklist(
                data
            ),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    unknown_path.write_text(
        "\n".join(
            unknown_lines
        ),
        encoding="utf-8",
    )

    print()
    print("=== Friday Zoom Intake ===")

    for field, record in data.items():
        print(
            f"{field:<24} "
            f"{record['status']}"
        )

    print()
    print(
        f"intake : {intake_path}"
    )
    print(
        f"bible  : {bible_path}"
    )
    print(
        f"media  : {media_path}"
    )
    print(
        f"unknown: {unknown_path}"
    )

    if unknown_lines:
        print()
        print(
            "WARN: unrecognized lines "
            f"= {len(unknown_lines)}"
        )


if __name__ == "__main__":
    main()
