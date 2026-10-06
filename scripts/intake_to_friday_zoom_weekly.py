from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml


WEEK_FIELDS = {
    "opening_songs",
    "first_prayer",
    "song_after_prayer",
    "scripture",
    "sermon_title",
    "additional_scripture",
    "response_song",
    "word_prayer",
    "intercession_song",
    "community_prayer",
    "personal_prayer",
}


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--intake",
        required=True,
    )

    # 구조 참고용이다.
    # 과거 주차의 실제 내용을 승계하지 않는다.
    parser.add_argument(
        "--schema",
        default=(
            "samples/weekly/"
            "friday-zoom-20260918.yaml"
        ),
    )

    parser.add_argument(
        "--output",
    )

    return parser.parse_args()


def record(
    intake,
    name,
):
    return intake["fields"][name]


def require_no_missing(
    intake,
):
    if intake.get(
        "review_required",
        False,
    ):
        print()
        print(
            "STOP: The notice contains unrecognized content. "
            "Manual review is required."
        )

        for item in intake.get(
            "review_items",
            [],
        ):
            print(
                f"  REVIEW: {item}"
            )

        print()
        print(
            "Do not finalize the weekly YAML until "
            "all review items are resolved."
        )

        raise SystemExit(3)

    missing = []

    if (
        intake["date"]["status"]
        == "missing"
    ):
        missing.append("date")

    for name, value in (
        intake["fields"].items()
    ):
        if value["status"] == "missing":
            missing.append(name)

    if missing:
        print()
        print(
            "STOP: 안내에 아예 없는 항목이 있습니다."
        )

        for name in missing:
            print(
                f"  - {name}"
            )

        print()
        print(
            "지난주 자료로 자동 보충하지 않습니다."
        )
        print(
            "이번 주에 정말 없는 항목이라면 "
            "안내문에 '항목:' 형태로 빈 값을 "
            "명시해 주세요."
        )

        raise SystemExit(2)


def status_from_shape(
    shape,
    blank=False,
):
    if not isinstance(
        shape,
        dict,
    ):
        return None

    if "status" not in shape:
        return None

    # 기존 유효 샘플의 status 표현을
    # 가능한 한 그대로 활용한다.
    current = shape["status"]

    if blank:
        # intake? blank?
        # Convert an explicitly blank intake field to WeeklyStatus.NONE.
        return "NONE"

    if str(current).lower() in {
        "value",
        "provided",
    }:
        return current

    return "value"


def song_value(
    shape,
    title,
):
    if isinstance(
        shape,
        str,
    ):
        return title

    result = {}

    if isinstance(
        shape,
        dict,
    ):
        if "status" in shape:
            result["status"] = (
                status_from_shape(
                    shape
                )
            )

        if "title" in shape:
            result["title"] = title
        elif "text" in shape:
            result["text"] = title
        elif "value" in shape:
            result["value"] = title
        else:
            result["title"] = title

        return result

    return {
        "title": title,
    }


def prayer_value(
    shape,
    values,
):
    values = list(values or [])

    result = {}

    if isinstance(
        shape,
        dict,
    ):
        if "status" in shape:
            result["status"] = (
                status_from_shape(
                    shape
                )
            )

        if "topics" in shape:
            result["topics"] = values

        elif "items" in shape:
            result["items"] = values

        elif "text" in shape:
            result["text"] = (
                "\n".join(values)
            )

        elif "value" in shape:
            result["value"] = values

        else:
            result["topics"] = values

        return result

    return {
        "topics": values,
    }


def scripture_value(
    shape,
    rec,
):
    if rec["status"] == "blank":
        result = {}

        if isinstance(
            shape,
            dict,
        ):
            if "status" in shape:
                result["status"] = "NONE"

            if "reference" in shape:
                result["reference"] = None

            elif "value" in shape:
                result["value"] = None

            return result

        return None

    reference = rec["value"]

    result = {}

    if isinstance(
        shape,
        dict,
    ):
        if "status" in shape:
            result["status"] = (
                status_from_shape(
                    shape
                )
            )

        if "reference" in shape:
            result["reference"] = reference

        elif "value" in shape:
            result["value"] = reference

        else:
            result["reference"] = reference

        return result

    return reference


def sermon_value(
    shape,
    title,
    scripture_reference,
):
    result = {}

    if isinstance(
        shape,
        dict,
    ):
        if "status" in shape:
            result["status"] = (
                status_from_shape(
                    shape
                )
            )

        if "text" in shape:
            result["text"] = title
        elif "title" in shape:
            result["title"] = title
        else:
            result["text"] = title

        if (
            "scripture_reference"
            in shape
        ):
            result[
                "scripture_reference"
            ] = scripture_reference

        elif "reference" in shape:
            result[
                "reference"
            ] = scripture_reference

        return result

    return {
        "text": title,
        "scripture_reference":
            scripture_reference,
    }


def personal_prayer_value(
    shape,
    values,
):
    values = list(values or [])

    text = "\n".join(values)

    if isinstance(
        shape,
        dict,
    ):
        result = {}

        if "status" in shape:
            result["status"] = (
                status_from_shape(
                    shape
                )
            )

        if "text" in shape:
            result["text"] = text

        elif "value" in shape:
            result["value"] = text

        elif "topics" in shape:
            result["topics"] = values

        else:
            result["text"] = text

        return result

    return {
        "text": text,
    }


def main():
    args = parse_args()

    intake_path = Path(
        args.intake
    )

    schema_path = Path(
        args.schema
    )

    intake = yaml.safe_load(
        intake_path.read_text(
            encoding="utf-8-sig"
        )
    )

    schema = yaml.safe_load(
        schema_path.read_text(
            encoding="utf-8-sig"
        )
    )

    require_no_missing(
        intake
    )

    date_value = intake[
        "date"
    ]["value"]

    token = str(
        date_value
    ).replace(
        "-",
        "",
    )

    output_path = (
        Path(args.output)
        if args.output
        else Path(
            "output/friday_zoom_intake"
        )
        / (
            f"friday-zoom-"
            f"{token}.yaml"
        )
    )

    # ----------------------------------------
    # 새 주간 데이터 생성
    # ----------------------------------------
    #
    # schema 전체를 deepcopy 하지 않는다.
    # 정적 메타데이터만 유지하고,
    # 주차별 필드는 전부 새로 작성한다.
    # ----------------------------------------

    weekly = {
        key: copy.deepcopy(value)
        for key, value
        in schema.items()
        if (
            key not in WEEK_FIELDS
            and key != "date"
        )
    }

    weekly["date"] = date_value

    # ----------------------------------------
    # Opening songs
    # ----------------------------------------

    opening_shape = schema.get(
        "opening_songs",
        [],
    )

    item_shape = (
        opening_shape[0]
        if (
            isinstance(
                opening_shape,
                list,
            )
            and opening_shape
        )
        else {}
    )

    weekly["opening_songs"] = [
        song_value(
            item_shape,
            record(
                intake,
                "opening_song_1",
            )["value"],
        ),
        song_value(
            item_shape,
            record(
                intake,
                "opening_song_2",
            )["value"],
        ),
    ]

    # ----------------------------------------
    # Prayer 1
    # ----------------------------------------

    weekly["first_prayer"] = (
        prayer_value(
            schema.get(
                "first_prayer",
                {},
            ),
            record(
                intake,
                "first_prayer",
            )["value"],
        )
    )

    # ----------------------------------------
    # Song after prayer
    # ----------------------------------------

    weekly[
        "song_after_prayer"
    ] = song_value(
        schema.get(
            "song_after_prayer",
            {},
        ),
        record(
            intake,
            "song_after_prayer",
        )["value"],
    )

    # ----------------------------------------
    # Scripture
    # ----------------------------------------

    scripture_record = record(
        intake,
        "scripture",
    )

    weekly["scripture"] = (
        scripture_value(
            schema.get(
                "scripture",
                {},
            ),
            scripture_record,
        )
    )

    scripture_reference = (
        scripture_record["value"]
    )

    # ----------------------------------------
    # Sermon title
    # ----------------------------------------

    weekly[
        "sermon_title"
    ] = sermon_value(
        schema.get(
            "sermon_title",
            {},
        ),
        record(
            intake,
            "sermon_title",
        )["value"],
        scripture_reference,
    )

    # ----------------------------------------
    # Additional scripture
    # ----------------------------------------

    weekly[
        "additional_scripture"
    ] = scripture_value(
        schema.get(
            "additional_scripture",
            {},
        ),
        record(
            intake,
            "additional_scripture",
        ),
    )

    # ----------------------------------------
    # Response song
    # ----------------------------------------

    weekly[
        "response_song"
    ] = song_value(
        schema.get(
            "response_song",
            {},
        ),
        record(
            intake,
            "response_song",
        )["value"],
    )

    # ----------------------------------------
    # Word prayer
    # ----------------------------------------

    weekly[
        "word_prayer"
    ] = prayer_value(
        schema.get(
            "word_prayer",
            {},
        ),
        record(
            intake,
            "word_prayer",
        )["value"],
    )

    # ----------------------------------------
    # Intercession song
    # ----------------------------------------

    weekly[
        "intercession_song"
    ] = song_value(
        schema.get(
            "intercession_song",
            {},
        ),
        record(
            intake,
            "intercession_song",
        )["value"],
    )

    # ----------------------------------------
    # Community prayer
    # ----------------------------------------

    weekly[
        "community_prayer"
    ] = prayer_value(
        schema.get(
            "community_prayer",
            {},
        ),
        record(
            intake,
            "community_prayer",
        )["value"],
    )

    # ----------------------------------------
    # Personal prayer
    # ----------------------------------------

    weekly[
        "personal_prayer"
    ] = personal_prayer_value(
        schema.get(
            "personal_prayer",
            {},
        ),
        record(
            intake,
            "personal_prayer",
        )["value"],
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        yaml.safe_dump(
            weekly,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=== Friday Zoom Weekly YAML ==="
    )
    print(
        f"source : {intake_path}"
    )
    print(
        f"schema : {schema_path}"
    )
    print(
        f"output : {output_path}"
    )
    print()
    print(
        "OK: 과거 주차의 주간 내용은 "
        "자동 승계하지 않았습니다."
    )


if __name__ == "__main__":
    main()
