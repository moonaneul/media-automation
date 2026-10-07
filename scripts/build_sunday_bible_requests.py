from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from media_automation.weekly_data.models import SundayData, WeeklyStatus, parse_weekly_data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--weekly", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    weekly_path = Path(args.weekly)
    raw = yaml.safe_load(weekly_path.read_text(encoding="utf-8-sig")) or {}
    weekly = parse_weekly_data(raw)
    if not isinstance(weekly, SundayData):
        raise TypeError("--weekly에는 주일예배 데이터가 필요합니다.")

    requests = []
    for source, field in (
        ("scripture", weekly.worship.scripture),
        ("additional_scripture", weekly.worship.additional_scripture),
    ):
        if field.status != WeeklyStatus.VALUE:
            continue
        requests.append(
            {
                "source": source,
                "reference": field.reference,
                "translation": "개역개정",
                "display_rule": "세례→침례",
            }
        )

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(
            {"requests": requests},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    print(f"SUNDAY BIBLE REQUESTS: {output}")


if __name__ == "__main__":
    main()
