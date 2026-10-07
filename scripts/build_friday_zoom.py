from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory

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
    build_friday_zoom_with_media,
    load_zoom_media_asset_provider,
    plan_friday_zoom_media_placements,
)
from media_automation.ppt.friday_zoom_postprocess import finalize_friday_zoom_powerpoint
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

    if not isinstance(raw, dict):
        raise ValueError(
            "Bible YAML 형식이 잘못되었습니다."
        )

    passages_raw = raw.get("passages")

    if not isinstance(
        passages_raw,
        dict,
    ):
        raise ValueError(
            "Bible YAML에 passages가 필요합니다."
        )

    passages = {}

    for lookup_reference, data in (
        passages_raw.items()
    ):
        verses = tuple(
            BibleVerse(
                number=int(number),
                text=text,
                end_number=(data.get("verse_ends", {}).get(number)
                            or data.get("verse_ends", {}).get(str(number))),
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


def print_placements(
    placements,
) -> None:
    print()
    print(
        "=== Media Placements ==="
    )

    for placement in placements:
        asset = placement.asset

        print(
            f"slide {placement.slide_number:>2} | "
            f"{asset.media_type.value:<5} | "
            f"{placement.block_key:<22} | "
            f"{asset.path.name}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "하늘빛기쁨성서침례교회 "
            "금요기도회 Zoom PPT 제작"
        )
    )

    parser.add_argument(
        "--weekly",
        type=Path,
        required=True,
        help="이번 주 금요 Zoom YAML",
    )

    parser.add_argument(
        "--bible",
        type=Path,
        required=True,
        help="이번 주 개역개정 본문 YAML",
    )

    parser.add_argument(
        "--media",
        type=Path,
        required=True,
        help="MP4/MP3 media manifest YAML",
    )

    parser.add_argument(
        "--include-pre-service-audio",
        action="store_true",
        help=(
            "Prayer audio mapping is incomplete: "
            "At least one required audio file is missing."
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="최종 PPT 출력 경로",
    )

    parser.add_argument(
        "--validate-only",
        action="store_true",
        help=(
            "입력 자료와 미디어 배치만 검증하고 "
            "최종 PPT는 생성하지 않음"
        ),
    )

    args = parser.parse_args()

    for name, path in {
        "weekly": args.weekly,
        "bible": args.bible,
        "media": args.media,
    }.items():
        if not path.exists():
            raise FileNotFoundError(
                f"{name} 파일이 없습니다: {path}"
            )

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

    if args.validate_only:
        # 슬라이드 번호 계산을 위해 임시 PPT를
        # 생성하지만 작업 폴더에는 남기지 않는다.
        with TemporaryDirectory() as temp_dir:
            temp_output = (
                Path(temp_dir)
                / "friday_zoom_structure.pptx"
            )

            structure = (
                build_friday_zoom_structure(
                    plan,
                    temp_output,
                    bible_provider=(
                        bible_provider
                    ),
                )
            )

            placements = (
                plan_friday_zoom_media_placements(
                    plan,
                    structure.slide_ranges,
                    media_provider,
                    include_pre_service_audio=(
                        args.include_pre_service_audio
                    ),
                )
            )

            slide_count = max(
                item.end
                for item
                in structure.slide_ranges.values()
            )

        print()
        print(
            "=== Friday Zoom Validation ==="
        )

        print(
            f"weekly : {args.weekly}"
        )
        print(
            f"bible  : {args.bible}"
        )
        print(
            f"media  : {args.media}"
        )

        print()
        print(
            f"plan blocks : {len(plan)}"
        )
        print(
            f"slides : {slide_count}"
        )
        print(
            "media placements : "
            f"{len(placements)}"
        )

        print_placements(
            placements
        )

        print()
        print(
            "금요 Zoom 제작 입력 검증 완료."
        )
        print(
            "최종 PPT는 생성하지 않았습니다."
        )
        print(
            "PowerPoint 실제 미디어 재생은 "
            "별도 검수 항목입니다."
        )

        return

    if args.output is None:
        parser.error(
            "--validate-only가 아니면 "
            "--output이 필요합니다."
        )

    result = build_friday_zoom_with_media(
        plan,
        args.output,
        bible_provider=bible_provider,
        media_provider=media_provider,
        include_pre_service_audio=(
            args.include_pre_service_audio
        ),
    )

    animation_count = (
        finalize_friday_zoom_powerpoint(
            result.output_path,
            weekly=weekly,
            slide_ranges=result.slide_ranges,
        )
    )

    print()
    print(
        "=== Friday Zoom Build ==="
    )

    print(
        f"output : {result.output_path}"
    )
    print(
        "media placements : "
        f"{len(result.media_placements)}"
    )

    print_placements(
        result.media_placements
    )

    print(
        "prayer animations : "
        f"{animation_count}"
    )

    print()
    print(
        "금요 Zoom PPT 생성 및 "
        "미디어 삽입 완료."
    )
    print(
        "주의: 실제 PowerPoint 재생 검수는 "
        "별도로 진행해야 합니다."
    )


if __name__ == "__main__":
    main()