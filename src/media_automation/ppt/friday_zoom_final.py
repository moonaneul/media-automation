from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from media_automation.bible import (
    BibleProvider,
)
from media_automation.planning import (
    WorshipBlock,
)

from .friday_zoom_builder import (
    FridayZoomSlideRange,
    build_friday_zoom_structure,
)
from .friday_zoom_media_plan import (
    FridayZoomMediaPlacement,
    plan_friday_zoom_media_placements,
)
from .media_embed import (
    MediaEmbedRequest,
    MediaEmbedder,
    create_platform_media_embedder,
)
from .zoom_media_assets import (
    ZoomMediaAssetProvider,
)


@dataclass(frozen=True, slots=True)
class FridayZoomFinalBuildResult:
    output_path: Path
    slide_ranges: dict[
        str,
        FridayZoomSlideRange,
    ]
    media_placements: list[
        FridayZoomMediaPlacement
    ]


def build_friday_zoom_with_media(
    plan: list[WorshipBlock],
    output_path: str | Path,
    *,
    bible_provider: BibleProvider,
    media_provider: ZoomMediaAssetProvider,
    media_embedder: MediaEmbedder | None = None,
    include_pre_service_audio: bool = False,
) -> FridayZoomFinalBuildResult:
    """
    금요 Zoom 최종 PPT 제작 흐름.

    1. 16:9 PPT 구조 생성
    2. block -> slide 번호 확정
    3. media manifest -> 삽입 위치 계산
    4. MP4/MP3 삽입

    PowerPoint 실제 재생 성공 여부는
    별도 검수 항목이다.
    """

    # Mac에서 기본 실행했다가
    # 미디어 없는 PPT만 남는 것을 막기 위해
    # embedder 지원 여부를 먼저 확인한다.
    if media_embedder is None:
        media_embedder = (
            create_platform_media_embedder()
        )

    structure = build_friday_zoom_structure(
        plan,
        output_path,
        bible_provider=bible_provider,
    )

    placements = (
        plan_friday_zoom_media_placements(
            plan,
            structure.slide_ranges,
            media_provider,
            include_pre_service_audio=(
                include_pre_service_audio
            ),
        )
    )

    requests = [
        MediaEmbedRequest(
            slide_number=(
                placement.slide_number
            ),
            asset=placement.asset,
        )
        for placement in placements
    ]

    media_embedder.embed_many(
        structure.output_path,
        requests=requests,
    )

    return FridayZoomFinalBuildResult(
        output_path=structure.output_path,
        slide_ranges=structure.slide_ranges,
        media_placements=placements,
    )