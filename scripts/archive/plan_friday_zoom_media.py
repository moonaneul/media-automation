from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from media_automation.bible import (
    BiblePassage,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    build_friday_zoom_plan,
)
from media_automation.ppt import (
    build_friday_zoom_structure,
    load_zoom_media_asset_provider,
    plan_friday_zoom_media_placements,
)
from media_automation.weekly_data.models import (
    FridayZoomData,
    parse_weekly_data,
)


def load_weekly(
    path: Path,
) -> FridayZoomData:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    weekly = parse_weekly_data(raw)

    if not isinstance(
        weekly,
        FridayZoomData,
    ):
        raise TypeError(
            "금요 Zoom weekly YAML이 필요합니다."
        )

    return weekly


def load_bible(
    path: Path,
) -> InMemoryBibleProvider:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    passages = {}

    for lookup_reference, data in (
        raw["passages"].items()
    ):
        verses = tuple(
            BibleVerse(
                number=int(number),
                text=text,
            )
            for number, text
            in data["verses"].items()
        )

        passages[
            lookup_reference
        ] = BiblePassage(
            reference=data["reference"],
            verses=verses,
        )

    return InMemoryBibleProvider(
        passages
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "금요 Zoom 미디어 삽입 위치 dry-run"
        )
    )

    parser.add_argument(
        "--weekly",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--bible",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--media",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help=(
            "미디어 삽입 전 구조 확인용 PPT"
        ),
    )

    args = parser.parse_args()

    weekly = load_weekly(
        args.weekly
    )

    bible_provider = load_bible(
        args.bible
    )

    media_provider = (
        load_zoom_media_asset_provider(
            args.media
        )
    )

    plan = build_friday_zoom_plan(
        weekly
    )

    structure = (
        build_friday_zoom_structure(
            plan,
            args.output,
            bible_provider=bible_provider,
        )
    )

    placements = (
        plan_friday_zoom_media_placements(
            plan,
            structure.slide_ranges,
            media_provider,
        )
    )

    print()
    print(
        "=== Friday Zoom Media Dry Run ==="
    )

    print(
        f"weekly : {args.weekly}"
    )
    print(
        f"media  : {args.media}"
    )
    print(
        f"output : {args.output}"
    )

    print()
    print(
        f"plan blocks : {len(plan)}"
    )

    print(
        "media placements : "
        f"{len(placements)}"
    )

    print()
    print(
        "=== Slide Media Placements ==="
    )

    for placement in placements:
        asset = placement.asset

        print(
            f"slide {placement.slide_number:>2} | "
            f"{asset.media_type.value:<5} | "
            f"{placement.block_key:<22} | "
            f"{placement.media_key:<24} | "
            f"{asset.path.name}"
        )

    print()
    print(
        "미디어 삽입 위치 계산 완료."
    )
    print(
        "주의: 실제 PowerPoint 미디어 삽입 및 "
        "재생 검증은 수행하지 않았습니다."
    )


if __name__ == "__main__":
    main()
