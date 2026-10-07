from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from media_automation.bulletin.merge import merge_bulletin_transfer
from media_automation.bulletin.transfer import parse_bulletin_transfer_text
from media_automation.weekly_data.models import SundayData, parse_weekly_data


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def preserve_notice_priority(
    *,
    base: SundayData,
    merged: SundayData,
    intake: dict,
) -> SundayData:
    """
    전달 주보는 안내에서 아예 빠진(missing) 항목만 보완한다.

    안내의 provided/blank는 최신 주일예배 안내로 간주하여
    전달 주보보다 우선한다.
    """
    fields = intake.get("fields", {})

    worship = merged.worship
    serving = merged.serving
    bulletin = merged.bulletin

    if fields.get("additional_scripture", {}).get("status") != "missing":
        worship = worship.model_copy(
            update={
                "additional_scripture": base.worship.additional_scripture,
            }
        )

    second = serving.this_week.second_service
    base_second = base.serving.this_week.second_service

    if fields.get("second_service_prayer", {}).get("status") != "missing":
        second = second.model_copy(
            update={"prayer": base_second.prayer}
        )

    if (
        fields.get("second_service_offering_prayer", {}).get("status")
        != "missing"
    ):
        second = second.model_copy(
            update={"offering_prayer": base_second.offering_prayer}
        )

    this_week = serving.this_week.model_copy(
        update={"second_service": second}
    )
    serving = serving.model_copy(
        update={"this_week": this_week}
    )

    if fields.get("church_news", {}).get("status") != "missing":
        bulletin = bulletin.model_copy(
            update={"church_news": base.bulletin.church_news}
        )

    return merged.model_copy(
        update={
            "worship": worship,
            "serving": serving,
            "bulletin": bulletin,
        }
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--intake", required=True)
    parser.add_argument("--transfer-text", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base_raw = load(Path(args.base))
    base = parse_weekly_data(base_raw)
    if not isinstance(base, SundayData):
        raise TypeError("--base에는 주일예배 데이터가 필요합니다.")

    intake = load(Path(args.intake))
    transfer_text = Path(args.transfer_text).read_text(
        encoding="utf-8-sig"
    )
    transfer = parse_bulletin_transfer_text(
        transfer_text,
        year=base.date.year,
    )

    result = merge_bulletin_transfer(base, transfer)
    merged = preserve_notice_priority(
        base=base,
        merged=result.sunday,
        intake=intake,
    )

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
