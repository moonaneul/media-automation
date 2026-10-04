from __future__ import annotations

from dataclasses import dataclass

from media_automation.planning import (
    WorshipBlock,
)

from .friday_zoom_builder import (
    FridayZoomSlideRange,
)
from .friday_zoom_media import (
    get_friday_zoom_media_key,
    get_friday_zoom_media_type,
)
from .zoom_media_assets import (
    InvalidZoomMediaAssetError,
    ZoomMediaAsset,
    ZoomMediaAssetProvider,
    ZoomMediaType,
)


@dataclass(frozen=True, slots=True)
class FridayZoomMediaPlacement:
    block_key: str
    slide_number: int
    media_key: str
    asset: ZoomMediaAsset


def plan_friday_zoom_media_placements(
    plan: list[WorshipBlock],
    slide_ranges: dict[
        str,
        FridayZoomSlideRange,
    ],
    media_provider: ZoomMediaAssetProvider,
    *,
    include_pre_service_audio: bool = False,
) -> list[FridayZoomMediaPlacement]:
    """
    WorshipBlock과 실제 생성 슬라이드 범위를
    미디어 삽입 위치로 변환한다.

    현재 원칙:
    - ZOOM_SONG -> 해당 1장에 VIDEO
    - 기도 화면 -> 해당 1장에 AUDIO
    - pre_service audio는 기본 제외
      (기존 09-11/09-18 자료의 해당 자산이 CRC 오류)
    """

    placements: list[
        FridayZoomMediaPlacement
    ] = []

    for block in plan:
        if (
            block.key == "pre_service"
            and not include_pre_service_audio
        ):
            continue

        media_key = (
            get_friday_zoom_media_key(
                block
            )
        )
        expected_type = (
            get_friday_zoom_media_type(
                block
            )
        )

        if (
            media_key is None
            or expected_type is None
        ):
            continue

        slide_range = slide_ranges.get(
            block.key
        )

        if slide_range is None:
            raise RuntimeError(
                "미디어 블록의 슬라이드 범위를 "
                "찾을 수 없습니다: "
                f"{block.key}"
            )

        if (
            slide_range.start
            != slide_range.end
        ):
            raise RuntimeError(
                "미디어를 삽입할 블록은 현재 "
                "1개 슬라이드여야 합니다: "
                f"{block.key} -> "
                f"{slide_range.start}-"
                f"{slide_range.end}"
            )

        asset = (
            media_provider.get_media_asset(
                media_key
            )
        )

        if (
            asset.media_type
            != expected_type
        ):
            raise InvalidZoomMediaAssetError(
                "금요 Zoom 미디어 유형이 "
                "블록 규칙과 일치하지 않습니다: "
                f"{block.key} -> "
                f"{asset.media_type.value}, "
                f"expected="
                f"{expected_type.value}"
            )

        placements.append(
            FridayZoomMediaPlacement(
                block_key=block.key,
                slide_number=(
                    slide_range.start
                ),
                media_key=media_key,
                asset=asset,
            )
        )

    return placements