from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from media_automation.bulletin.merge import merge_bulletin_transfer
from media_automation.bulletin.source import read_transfer
from media_automation.bulletin.transfer import parse_bulletin_transfer_text
from media_automation.bulletin.weekly import merge_for_sunday
from media_automation.weekly_data.models import SundayData, parse_weekly_data


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--intake", required=True)
    parser.add_argument("--transfer-text", required=True, help="전달 주보 TXT/HWP/HWPX 원본")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base_raw = load(Path(args.base))
    base = parse_weekly_data(base_raw)
    if not isinstance(base, SundayData):
        raise TypeError("--base에는 주일예배 데이터가 필요합니다.")

    intake = load(Path(args.intake))
    transfer_text = read_transfer(Path(args.transfer_text))
    transfer = parse_bulletin_transfer_text(
        transfer_text,
        year=base.date.year,
    )

    result = merge_bulletin_transfer(base, transfer)
    merged = merge_for_sunday(base, transfer, intake)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(
            merged.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print(f"SUNDAY MERGED WEEKLY READY: {output}")
    print(f"transfer date : {transfer.date}")
    print(f"notice date   : {base.date}")

    if result.praise_raw.status.value == "VALUE":
        print(
            "NOTE: 전달 주보의 '찬양' 값은 주일 PPT의 개별 악보 슬롯에 "
            "임의 매핑하지 않았습니다."
        )
        print(f"praise raw: {result.praise_raw.value}")


if __name__ == "__main__":
    main()
