from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from pptx import Presentation

from media_automation.bible import (
    BiblePassage,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    build_friday_zoom_plan,
)
from media_automation.ppt import (
    build_friday_zoom_preview,
)
from media_automation.weekly_data.models import (
    FridayZoomData,
    parse_weekly_data,
)


def load_bible_provider(
    path: Path,
) -> InMemoryBibleProvider:
    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(
            "Bible YAML의 최상위 값은 객체여야 합니다."
        )

    passages_raw = raw.get("passages")

    if not isinstance(passages_raw, dict):
        raise ValueError(
            "Bible YAML에 passages 객체가 필요합니다."
        )

    passages: dict[str, BiblePassage] = {}

    for lookup_reference, data in passages_raw.items():
        if not isinstance(
            lookup_reference,
            str,
        ):
            raise ValueError(
                "Bible passage key는 "
                "문자열이어야 합니다."
            )

        if not isinstance(data, dict):
            raise ValueError(
                f"{lookup_reference}의 "
                "데이터 형식이 잘못되었습니다."
            )

        display_reference = data.get(
            "reference"
        )

        verses_raw = data.get(
            "verses"
        )

        if not isinstance(
            display_reference,
            str,
        ):
            raise ValueError(
                f"{lookup_reference}의 "
                "reference가 필요합니다."
            )

        if not isinstance(
            verses_raw,
            dict,
        ):
            raise ValueError(
                f"{lookup_reference}의 "
                "verses가 필요합니다."
            )

        verses: list[BibleVerse] = []

        for number_raw, text in (
            verses_raw.items()
        ):
            try:
                number = int(
                    number_raw
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    f"{lookup_reference}의 "
                    "절 번호가 잘못되었습니다: "
                    f"{number_raw}"
                ) from error

            if not isinstance(text, str):
                raise ValueError(
                    f"{lookup_reference} "
                    f"{number}절 본문은 "
                    "문자열이어야 합니다."
                )

            verses.append(
                BibleVerse(
                    number=number,
                    text=text,
                )
            )

        verses.sort(
            key=lambda verse: (
                verse.number
            )
        )

        passages[
            lookup_reference
        ] = BiblePassage(
            reference=display_reference,
            verses=tuple(verses),
        )

    return InMemoryBibleProvider(
        passages
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "하늘빛기쁨성서침례교회 "
            "금요 Zoom 구조 검수용 "
            "16:9 PPT 생성"
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
        "--output",
        type=Path,
        required=True,
        help="생성할 preview PPTX",
    )

    args = parser.parse_args()

    # -------------------------
    # 입력 파일 확인
    # -------------------------

    for name, path in {
        "weekly": args.weekly,
        "bible": args.bible,
    }.items():
        if not path.exists():
            raise FileNotFoundError(
                f"{name} 파일을 찾을 수 "
                f"없습니다: {path}"
            )

    # -------------------------
    # Weekly Data
    # -------------------------

    with args.weekly.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    weekly = parse_weekly_data(
        raw
    )

    if not isinstance(
        weekly,
        FridayZoomData,
    ):
        raise TypeError(
            "--weekly에는 "
            "금요 Zoom 데이터가 필요합니다."
        )

    plan = build_friday_zoom_plan(
        weekly
    )

    # -------------------------
    # Bible
    # -------------------------

    bible_provider = (
        load_bible_provider(
            args.bible
        )
    )

    # -------------------------
    # PPT 생성
    # -------------------------

    result = build_friday_zoom_preview(
        plan,
        args.output,
        bible_provider=bible_provider,
    )

    # -------------------------
    # 생성 결과 구조 검증
    # -------------------------

    prs = Presentation(
        result
    )

    ratio = (
        prs.slide_width
        / prs.slide_height
    )

    zoom_song_count = sum(
        1
        for block in plan
        if block.kind.value
        == "zoom_song"
    )

    print()
    print(
        "=== Friday Zoom Preview ==="
    )

    print(
        f"weekly : {args.weekly}"
    )
    print(
        f"bible  : {args.bible}"
    )
    print(
        f"output : {result}"
    )

    print()
    print(
        f"plan blocks : {len(plan)}"
    )
    print(
        f"zoom songs skipped : "
        f"{zoom_song_count}"
    )
    print(
        f"preview slides : "
        f"{len(prs.slides)}"
    )
    print(
        f"aspect ratio : "
        f"{ratio:.2f}"
    )

    print()
    print(
        "금요 Zoom 구조 검수용 "
        "PPT 생성 완료."
    )

    print(
        "주의: 찬양 영상/음원은 "
        "아직 삽입하지 않았습니다."
    )

    print(
        "이 파일은 최종 예배용 "
        "PPT가 아닙니다."
    )


if __name__ == "__main__":
    main()