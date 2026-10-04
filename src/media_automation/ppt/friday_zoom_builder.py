from __future__ import annotations

from pathlib import Path

from pptx import Presentation

from media_automation.bible import BibleProvider
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)

from .base import create_16x9_presentation
from .friday_zoom import (
    add_zoom_centered_text_slide,
    render_friday_zoom_block,
)


ZOOM_PREVIEW_SUPPORTED_BLOCK_KINDS = {
    BlockKind.PRE_SERVICE,
    BlockKind.ZOOM_SONG,
    BlockKind.BLANK,
    BlockKind.PRAYER_TOPICS,
    BlockKind.SCRIPTURE,
    BlockKind.SERMON_TITLE,
    BlockKind.PERSONAL_PRAYER,
}


def _make_preview_plan(
    plan: list[WorshipBlock],
) -> list[WorshipBlock]:
    """
    영상이 아직 삽입되지 않은 금요 Zoom 구조 미리보기용 Plan.

    ZOOM_SONG은 실제 화면에 임의 대체물을 만들지 않고 생략한다.
    영상 생략 때문에 BLANK가 연속되면 한 장으로 정리한다.
    """

    result: list[WorshipBlock] = []

    for block in plan:
        # 영상은 아직 실제 삽입 기능이 없으므로
        # 제목 화면 등으로 대체하지 않는다.
        if block.kind == BlockKind.ZOOM_SONG:
            continue

        if block.kind == BlockKind.BLANK:
            if not result:
                continue

            if result[-1].kind in {
                BlockKind.BLANK,
                BlockKind.PRE_SERVICE,
            }:
                continue

        result.append(block)

    # 마지막 순서가 영상이어서
    # BLANK만 남는 경우 제거
    if (
        result
        and result[-1].kind == BlockKind.BLANK
    ):
        result.pop()

    return result


def build_friday_zoom_preview(
    plan: list[WorshipBlock],
    output_path: str | Path,
    *,
    bible_provider: BibleProvider,
) -> Path:
    """
    금요 Zoom 구조 확인용 16:9 PPT를 만든다.

    현재 포함:
    - 예배 준비
    - 빈 화면
    - 기도 제목
    - 성경 본문
    - 설교 제목
    - 개인 기도

    현재 제외:
    - 실제 찬양 영상/음원

    따라서 이 결과물은 최종 예배용 PPT가 아니다.
    """

    output_path = Path(output_path)

    unsupported = [
        block
        for block in plan
        if block.kind
        not in ZOOM_PREVIEW_SUPPORTED_BLOCK_KINDS
    ]

    if unsupported:
        kinds = ", ".join(
            f"{block.kind}:{block.key}"
            for block in unsupported
        )

        raise ValueError(
            "금요 Zoom preview가 지원하지 않는 "
            f"블록이 있습니다: {kinds}"
        )

    preview_plan = _make_preview_plan(
        plan
    )

    prs = create_16x9_presentation()

    for block in preview_plan:
        if block.kind == BlockKind.PRE_SERVICE:
            add_zoom_centered_text_slide(
                prs,
                "예배 준비",
                font_size=36,
            )
            continue

        render_friday_zoom_block(
            prs,
            block,
            bible_provider=bible_provider,
            include_scripture_reference_slide=(
                block.kind == BlockKind.SCRIPTURE
                and block.key == "scripture"
            ),
        )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    prs.save(output_path)

    return output_path