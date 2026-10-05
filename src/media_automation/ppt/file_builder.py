from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from media_automation.bible import BibleProvider
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)

from .assets import PreServiceSlideProvider
from .base import create_4x3_presentation
from .builder import (
    UnsupportedPlanBlock,
    UnsupportedPlanError,
)
from .renderer import (
    MissingRenderDependencyError,
    render_block,
)
from .slide_merge import SlideMerger
from .song_assets import (
    MissingSongAssetError,
    SongAsset,
    SongAssetProvider,
)


FILE_SUPPORTED_BLOCK_KINDS = {
    BlockKind.PRE_SERVICE,
    BlockKind.SONG,
    BlockKind.BLANK,
    BlockKind.PRAYER,
    BlockKind.SERMON_TITLE,
    BlockKind.CHURCH_NEWS,
    BlockKind.SCRIPTURE,
}


def build_presentation_file_from_plan(
    plan: list[WorshipBlock],
    output_path: str | Path,
    *,
    bible_provider: BibleProvider | None = None,
    pre_service_provider: PreServiceSlideProvider | None = None,
    song_asset_provider: SongAssetProvider | None = None,
    slide_merger: SlideMerger | None = None,
    skip_missing_songs: bool = False,
    preserve_blank_after_pre_service: bool = False,
    preserve_trailing_blank: bool = False,
) -> Path:
    """
    Worship Plan을 실제 PPTX 파일로 조립한다.

    SONG은 외부 PPT 병합이 필요하기 때문에
    일반 in-memory builder와 분리한다.

    생성 시작 전에 필요한 Provider와
    악보 자산을 먼저 검사한다.
    """

    output_path = Path(
        output_path
    )

    unsupported = [
        UnsupportedPlanBlock(
            kind=block.kind,
            key=block.key,
        )
        for block in plan
        if block.kind
        not in FILE_SUPPORTED_BLOCK_KINDS
    ]

    if unsupported:
        raise UnsupportedPlanError(
            unsupported
        )

    # -------------------------
    # dependency preflight
    # -------------------------

    needs_bible = any(
        block.kind
        == BlockKind.SCRIPTURE
        for block in plan
    )

    if (
        needs_bible
        and bible_provider is None
    ):
        raise MissingRenderDependencyError(
            "SCRIPTURE 블록이 있으므로 "
            "BibleProvider가 필요합니다."
        )

    needs_pre_service = any(
        block.kind
        == BlockKind.PRE_SERVICE
        for block in plan
    )

    if (
        needs_pre_service
        and pre_service_provider is None
    ):
        raise MissingRenderDependencyError(
            "PRE_SERVICE 블록이 있으므로 "
            "PreServiceSlideProvider가 필요합니다."
        )

    needs_song = any(
        block.kind
        == BlockKind.SONG
        for block in plan
    )

    if (
        needs_song
        and song_asset_provider is None
    ):
        raise MissingRenderDependencyError(
            "SONG 블록이 있으므로 "
            "SongAssetProvider가 필요합니다."
        )

    if (
        needs_song
        and slide_merger is None
    ):
        raise MissingRenderDependencyError(
            "SONG 블록이 있으므로 "
            "SlideMerger가 필요합니다."
        )

    # -------------------------
    # 모든 악보 생성 전에 확인
    # -------------------------

    resolved_song_assets: dict[
        int,
        SongAsset,
    ] = {}

    if song_asset_provider is not None:
        for index, block in enumerate(
            plan
        ):
            if (
                block.kind
                != BlockKind.SONG
            ):
                continue

            title = block.value.title

            try:
                resolved_song_assets[
                    index
                ] = (
                    song_asset_provider
                    .get_song_asset(
                        title
                    )
                )

            except MissingSongAssetError:
                if not skip_missing_songs:
                    raise

    # -------------------------
    # 실제 조립 대상 Plan 정리
    # -------------------------

    effective_plan: list[
        tuple[int, WorshipBlock]
    ] = []

    for index, block in enumerate(
        plan
    ):
        # 악보가 없는 찬양은
        # 실제 예배 화면에서 생략한다.
        if (
            block.kind
            == BlockKind.SONG
            and index
            not in resolved_song_assets
            and skip_missing_songs
        ):
            continue

        # 누락 찬양 때문에
        # BLANK가 연속되면 한 장만 유지한다.
        if (
            block.kind
            == BlockKind.BLANK
        ):
            if not effective_plan:
                continue

            previous_block = (
                effective_plan[-1][1]
            )

            if (
                previous_block.kind
                == BlockKind.BLANK
            ):
                continue

            if (
                previous_block.kind
                == BlockKind.PRE_SERVICE
                and not preserve_blank_after_pre_service
            ):
                continue

        effective_plan.append(
            (
                index,
                block,
            )
        )

    # 끝 순서가 사라져 BLANK만
    # 마지막에 남는 경우 제거한다.
    if (
        effective_plan
        and effective_plan[-1][1].kind
        == BlockKind.BLANK
        and not preserve_trailing_blank
    ):
        effective_plan.pop()

    # -------------------------
    # PRE_SERVICE 기반 PPT 생성
    # -------------------------

    pre_service_blocks = [
        block
        for block in plan
        if block.kind
        == BlockKind.PRE_SERVICE
    ]

    if len(
        pre_service_blocks
    ) > 1:
        raise ValueError(
            "PRE_SERVICE 블록은 "
            "하나만 사용할 수 있습니다."
        )

    if pre_service_blocks:
        pre_service_block = (
            pre_service_blocks[0]
        )

        prs = (
            pre_service_provider
            .create_presentation(
                pre_service_block.key
            )
        )

    else:
        prs = (
            create_4x3_presentation()
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # -------------------------
    # 순서대로 실제 조립
    # -------------------------

    for index, block in effective_plan:

        if (
            block.kind
            == BlockKind.PRE_SERVICE
        ):
            # 이미 base Presentation에 포함됨
            continue

        if (
            block.kind
            == BlockKind.SONG
        ):
            asset = (
                resolved_song_assets.get(
                    index
                )
            )

            if asset is None:
                continue

            prs.save(
                output_path
            )

            after_slide = len(
                prs.slides
            )

            if (
                asset.start_slide
                is not None
                and asset.end_slide
                is not None
            ):
                slide_merger.insert_range(
                    output_path,
                    asset.path,
                    after_slide=after_slide,
                    start_slide=(
                        asset.start_slide
                    ),
                    end_slide=(
                        asset.end_slide
                    ),
                )

            else:
                slide_merger.insert_all(
                    output_path,
                    asset.path,
                    after_slide=after_slide,
                )

            prs = Presentation(
                output_path
            )

            continue

        render_block(
            prs,
            block,
            bible_provider=bible_provider,
        )

    prs.save(
        output_path
    )

    return output_path