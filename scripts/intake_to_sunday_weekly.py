from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def require_parse_ready(intake):
    if intake.get("review_required"):
        print("STOP: REVIEW 항목을 먼저 처리해야 합니다.")
        for item in intake.get("review_items", []):
            print(f"  - {item}")
        raise SystemExit(3)

    if intake.get("date", {}).get("status") != "provided":
        raise SystemExit("STOP: 주일 안내에서 날짜를 확인할 수 없습니다.")


def song(record, *, fallback_title: str):
    status = record["status"]

    if status == "missing":
        return {"status": "UNSET"}

    if status == "blank":
        return {"status": "NONE"}

    if status == "asset_required":
        return {
            "status": "VALUE",
            "title": fallback_title,
        }

    raw = str(record["value"]).strip()
    hymn_number = None

    match = re.search(
        r"(?:새\s*찬송가\s*)?(\d{1,3})\s*장",
        raw,
    )
    if match:
        hymn_number = int(match.group(1))
        title = re.sub(
            r"\(?\s*(?:새\s*찬송가\s*)?\d{1,3}\s*장\s*\)?",
            "",
            raw,
        ).strip(" -:()")
        if not title:
            title = fallback_title
    else:
        title = raw

    result = {
        "status": "VALUE",
        "title": title,
    }

    if hymn_number is not None:
        result["hymn_number"] = hymn_number

    return result


def person(record):
    if record["status"] == "missing":
        return {"status": "UNSET"}

    if record["status"] == "blank":
        return {"status": "NONE"}

    return {
        "status": "VALUE",
        "person": str(record["value"]).strip(),
    }


def scripture(record):
    if record["status"] == "missing":
        return {"status": "UNSET"}

    if record["status"] == "blank":
        return {"status": "NONE"}

    return {
        "status": "VALUE",
        "reference": str(record["value"]).strip(),
    }


def text(record):
    if record["status"] == "missing":
        return {"status": "UNSET"}

    if record["status"] == "blank":
        return {"status": "NONE"}

    return {
        "status": "VALUE",
        "text": str(record["value"]).strip(),
    }


def church_news(record):
    if record["status"] == "missing":
        return {"status": "UNSET"}

    if record["status"] == "blank":
        return {"status": "NONE"}

    # PPT는 세부 광고 내용을 표시하지 않고 '교회 소식' 화면 존재 여부만
    # 사용한다. 전달 주보가 있으면 세부 items는 주보 데이터로 보완할 수 있다.
    return {
        "status": "VALUE",
        "items": [
            {
                "text": str(record["value"]).strip(),
            }
        ],
    }


def unset_person():
    return {"status": "UNSET"}


def extract_praise_leader(fields):
    leaders = []

    for name in (
        "opening_song_1",
        "opening_song_2",
        "opening_song_3",
    ):
        leader = fields[name].get("leader")
        if leader and leader not in leaders:
            leaders.append(leader)

    if len(leaders) == 1:
        return {
            "status": "VALUE",
            "person": leaders[0],
        }

    return unset_person()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    intake_path = Path(args.intake)
    intake = load(intake_path)
    require_parse_ready(intake)

    date_value = str(intake["date"]["value"])
    token = date_value.replace("-", "")
    output = (
        Path(args.output)
        if args.output
        else Path("output/sunday_intake")
        / f"sunday-{token}-base.yaml"
    )

    field = intake["fields"]

    weekly = {
        "service": "sunday",
        "date": date_value,
        "worship": {
            "leader": unset_person(),
            "praise_first": unset_person(),
            "praise_second": extract_praise_leader(field),
            "preacher": unset_person(),
            "closing_prayer": unset_person(),
            "opening_songs": [
                song(
                    field["opening_song_1"],
                    fallback_title="__opening_song_1__",
                ),
                song(
                    field["opening_song_2"],
                    fallback_title="__opening_song_2__",
                ),
                song(
                    field["opening_song_3"],
                    fallback_title="__opening_song_3__",
                ),
            ],
            "separate_hymn": song(
                field["separate_hymn"],
                fallback_title="__separate_hymn__",
            ),
            "offering_hymn": song(
                field["offering_hymn"],
                fallback_title="__offering_hymn__",
            ),
            "special_song": song(
                field["special_song"],
                fallback_title="__special_song__",
            ),
            "sermon_title": text(field["sermon_title"]),
            "scripture": scripture(field["scripture"]),
            "additional_scripture": scripture(
                field["additional_scripture"]
            ),
            "decision_hymn": song(
                field["decision_hymn"],
                fallback_title="__decision_hymn__",
            ),
        },
        "serving": {
            "this_week": {
                "first_service": {
                    "prayer": unset_person(),
                    "offering_prayer": unset_person(),
                },
                "second_service": {
                    "prayer": person(field["second_service_prayer"]),
                    "offering_prayer": person(
                        field["second_service_offering_prayer"]
                    ),
                },
                "dishwashing": unset_person(),
                "wednesday_prayer": unset_person(),
            },
            "next_week": {
                "first_service": {
                    "prayer": unset_person(),
                    "offering_prayer": unset_person(),
                },
                "second_service": {
                    "prayer": unset_person(),
                    "offering_prayer": unset_person(),
                },
                "dishwashing": unset_person(),
                "wednesday_prayer": unset_person(),
            },
        },
        "bulletin": {
            "number": {"status": "UNSET"},
            "church_news": church_news(field["church_news"]),
            "afternoon_service": {"status": "UNSET"},
            "monthly_schedule": {"status": "UNSET"},
            "cell_group": {"status": "UNSET"},
        },
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(
            weekly,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print(f"SUNDAY BASE WEEKLY READY: {output}")


if __name__ == "__main__":
    main()
