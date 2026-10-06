from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


FIELDS = (
    "opening_song_1",
    "opening_song_2",
    "opening_song_3",
    "prayer",
    "additional_song",
    "scripture",
    "sermon_title",
    "additional_scripture",
    "decision_hymn",
)


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def require_ready(intake):
    if intake.get("review_required"):
        print("STOP: REVIEW 항목을 먼저 처리해야 합니다.")
        for item in intake.get("review_items", []):
            print(f"  - {item}")
        raise SystemExit(3)

    missing = []
    if intake.get("date", {}).get("status") == "missing":
        missing.append("date")

    for field in FIELDS:
        if intake["fields"][field]["status"] == "missing":
            missing.append(field)

    if missing:
        print("STOP: 안내에 아예 없는 항목이 있습니다.")
        for field in missing:
            print(f"  - {field}")
        print("지난주 값을 자동 승계하지 않습니다.")
        raise SystemExit(2)


def song(record, *, fallback_title: str):
    status = record["status"]

    if status == "blank":
        return {"status": "NONE"}

    if status == "asset_required":
        # 실제 곡명은 해당 주 악보 PPT가 결정한다.
        # Weekly Data에는 자산 슬롯을 식별할 수 있는 내부 제목만 사용한다.
        return {
            "status": "VALUE",
            "title": fallback_title,
        }

    raw = str(record["value"]).strip()
    hymn_number = None

    # 예: 예수님은 누구신가(96장), 새찬송가 315장 내 주 되신 주를 참 사랑하고
    match = re.search(r"(?:새\s*찬송가\s*)?(\d{1,3})\s*장", raw)
    if match:
        hymn_number = int(match.group(1))
        title = re.sub(
            r"\(?\s*(?:새\s*찬송가\s*)?\d{1,3}\s*장\s*\)?",
            "",
            raw,
        ).strip(" -:()")
    else:
        title = raw

    result = {"status": "VALUE", "title": title}
    if hymn_number is not None:
        result["hymn_number"] = hymn_number
    return result


def person(record):
    if record["status"] == "blank":
        return {"status": "NONE"}
    return {"status": "VALUE", "person": str(record["value"]).strip()}


def scripture(record):
    if record["status"] == "blank":
        return {"status": "NONE"}
    return {"status": "VALUE", "reference": str(record["value"]).strip()}


def text(record):
    if record["status"] == "blank":
        return {"status": "NONE"}
    return {"status": "VALUE", "text": str(record["value"]).strip()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()

    intake_path = Path(args.intake)
    intake = load(intake_path)
    require_ready(intake)

    date_value = str(intake["date"]["value"])
    token = date_value.replace("-", "")
    output = (
        Path(args.output)
        if args.output
        else Path("output/wednesday_intake") / f"wednesday-{token}.yaml"
    )

    field = intake["fields"]
    weekly = {
        "service": "wednesday",
        "date": date_value,
        "opening_songs": [
            song(field["opening_song_1"], fallback_title="__opening_song_1__"),
            song(field["opening_song_2"], fallback_title="__opening_song_2__"),
            song(field["opening_song_3"], fallback_title="__opening_song_3__"),
        ],
        "prayer": person(field["prayer"]),
        "additional_song": song(
            field["additional_song"],
            fallback_title="__additional_song__",
        ),
        "scripture": scripture(field["scripture"]),
        "sermon_title": text(field["sermon_title"]),
        "additional_scripture": scripture(field["additional_scripture"]),
        "decision_hymn": song(
            field["decision_hymn"],
            fallback_title="__decision_hymn__",
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(weekly, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"WEDNESDAY WEEKLY READY: {output}")


if __name__ == "__main__":
    main()
