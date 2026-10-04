from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from media_automation.bible import (
    BiblePassage,
    BiblePassageNotFoundError,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    BlockKind,
    build_friday_zoom_plan,
)
from media_automation.weekly_data.models import (
    ChurchReview,
    FileStatus,
    FridayZoomData,
    TechnicalCheck,
    UsagePermission,
    parse_weekly_data,
)

from media_automation.ppt import (
    InvalidZoomMediaAssetError,
    MissingZoomMediaAssetError,
    load_zoom_media_asset_provider,
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
        if not isinstance(lookup_reference, str):
            raise ValueError(
                "Bible passage key는 문자열이어야 합니다."
            )

        if not isinstance(data, dict):
            raise ValueError(
                f"{lookup_reference}의 데이터 형식이 잘못되었습니다."
            )

        display_reference = data.get("reference")
        verses_raw = data.get("verses")

        if not isinstance(display_reference, str):
            raise ValueError(
                f"{lookup_reference}의 reference가 필요합니다."
            )

        if not isinstance(verses_raw, dict):
            raise ValueError(
                f"{lookup_reference}의 verses가 필요합니다."
            )

        verses: list[BibleVerse] = []

        for number_raw, text in verses_raw.items():
            try:
                number = int(number_raw)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    f"{lookup_reference}의 절 번호가 "
                    f"잘못되었습니다: {number_raw}"
                ) from error

            if not isinstance(text, str):
                raise ValueError(
                    f"{lookup_reference} {number}절 "
                    "본문은 문자열이어야 합니다."
                )

            verses.append(
                BibleVerse(
                    number=number,
                    text=text,
                )
            )

        verses.sort(
            key=lambda verse: verse.number
        )

        passages[lookup_reference] = BiblePassage(
            reference=display_reference,
            verses=tuple(verses),
        )

    return InMemoryBibleProvider(passages)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "하늘빛기쁨성서침례교회 "
            "금요기도회 Zoom 입력 검증"
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
        help=(
            "실제 금요 Zoom MP4/MP3 경로를 "
            "정의한 media manifest YAML"
        ),
    )
    args = parser.parse_args()

    for name, path in {
        "weekly": args.weekly,
        "bible": args.bible,
    }.items():
        if not path.exists():
            raise FileNotFoundError(
                f"{name} 파일을 찾을 수 없습니다: {path}"
            )
    if (
        args.media is not None
        and not args.media.exists()
    ):
        raise FileNotFoundError(
            "media manifest를 찾을 수 없습니다: "
            f"{args.media}"
        )

    # -------------------------
    # Weekly Data
    # -------------------------

    with args.weekly.open(
        "r",
        encoding="utf-8",
    ) as file:
        weekly_raw = yaml.safe_load(file)

    weekly = parse_weekly_data(
        weekly_raw
    )

    if not isinstance(
        weekly,
        FridayZoomData,
    ):
        raise TypeError(
            "--weekly에는 금요 Zoom 데이터가 필요합니다."
        )

    plan = build_friday_zoom_plan(
        weekly
    )

    # -------------------------
    # Bible
    # -------------------------

    bible_provider = load_bible_provider(
        args.bible
    )

    missing_bible_passages: list[str] = []

    for block in plan:
        if block.kind != BlockKind.SCRIPTURE:
            continue

        reference = block.value.reference

        try:
            bible_provider.get_passage(
                reference
            )
        except BiblePassageNotFoundError:
            missing_bible_passages.append(
                reference
            )

    if missing_bible_passages:
        print()
        print(
            "=== Missing Bible Passages ==="
        )

        for reference in missing_bible_passages:
            print(
                f"- {reference}"
            )

        raise RuntimeError(
            "필요한 개역개정 성경 본문이 "
            "Bible YAML에 없습니다."
        )

    # -------------------------
    # Zoom media 상태
    # -------------------------

    zoom_song_count = 0
    available_count = 0
    technical_verified_count = 0
    church_verified_count = 0
    permission_verified_count = 0

    missing_media: list[str] = []
    technical_pending: list[str] = []
    church_review_pending: list[str] = []
    permission_pending: list[str] = []

    for block in plan:
        if block.kind != BlockKind.ZOOM_SONG:
            continue

        song = block.value
        media = song.media

        zoom_song_count += 1

        if media.file_status == FileStatus.AVAILABLE:
            available_count += 1
        else:
            missing_media.append(
                song.title
            )

        if (
            media.technical_check
            == TechnicalCheck.VERIFIED
        ):
            technical_verified_count += 1
        else:
            technical_pending.append(
                song.title
            )

        if (
            media.church_review
            == ChurchReview.VERIFIED
        ):
            church_verified_count += 1
        else:
            church_review_pending.append(
                song.title
            )

        if (
            media.usage_permission
            == UsagePermission.VERIFIED
        ):
            permission_verified_count += 1
        else:
            permission_pending.append(
                song.title
            )
        # -------------------------
    # 실제 media manifest 검사
    # -------------------------

    actual_media_checked = False
    actual_media_ok: list[str] = []
    actual_media_missing: list[str] = []
    actual_media_invalid: list[str] = []

    if args.media is not None:
        actual_media_checked = True

        media_provider = (
            load_zoom_media_asset_provider(
                args.media
            )
        )

        for block in plan:
            if block.kind != BlockKind.ZOOM_SONG:
                continue

            title = block.value.title

            try:
                media_provider.get_media_asset(
                    title
                )

            except MissingZoomMediaAssetError:
                actual_media_missing.append(
                    title
                )

            except InvalidZoomMediaAssetError:
                actual_media_invalid.append(
                    title
                )

            else:
                actual_media_ok.append(
                    title
                )

    # -------------------------
    # 출력
    # -------------------------

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

    print()
    print(
        f"plan blocks : {len(plan)}"
    )
    print(
        f"zoom songs : {zoom_song_count}"
    )
    print(
        "bible passages : OK"
    )

    print()
    print(
        "=== Media Status ==="
    )

    print(
        "declared available : "
        f"{available_count}/{zoom_song_count}"
    )

    print(
        "technical verified : "
        f"{technical_verified_count}/{zoom_song_count}"
    )

    print(
        "church review verified : "
        f"{church_verified_count}/{zoom_song_count}"
    )

    print(
        "usage permission verified : "
        f"{permission_verified_count}/{zoom_song_count}"
    )

    if missing_media:
        print()
        print(
            "=== Missing Media ==="
        )

        for title in missing_media:
            print(f"- {title}")

    if technical_pending:
        print()
        print(
            "=== Technical Check Pending ==="
        )

        for title in technical_pending:
            print(f"- {title}")

    if church_review_pending:
        print()
        print(
            "=== Church Review Pending ==="
        )

        for title in church_review_pending:
            print(f"- {title}")

    if permission_pending:
        print()
        print(
            "=== Usage Permission Pending ==="
        )

        for title in permission_pending:
            print(f"- {title}")

    # 실제 manifest가 있을 때만
    # 디스크 파일 검사 결과 출력
    if actual_media_checked:
        print()
        print(
            "=== Actual Media Files ==="
        )

        print(
            "actual media OK : "
            f"{len(actual_media_ok)}/"
            f"{zoom_song_count}"
        )

        if actual_media_missing:
            print()
            print(
                "=== Actual Media Missing ==="
            )

            for title in actual_media_missing:
                print(f"- {title}")

        if actual_media_invalid:
            print()
            print(
                "=== Actual Media Invalid ==="
            )

            for title in actual_media_invalid:
                print(f"- {title}")

    print()
    print(
        "금요 Zoom 입력 검증 완료."
    )

    print(
        "주의: file_status=AVAILABLE은 "
        "주간 입력에 기록된 상태입니다."
    )

    if args.media is None:
        print(
            "실제 미디어 파일 존재 여부는 "
            "--media를 지정하면 추가 검증할 수 있습니다."
        )
    else:
        print(
            "실제 파일 존재 여부와 0바이트 여부까지 "
            "검사했습니다."
        )

    print(
        "PowerPoint에서의 실제 정상 재생 여부는 "
        "여전히 별도 검수 항목입니다."
    )


if __name__ == "__main__":
    main()