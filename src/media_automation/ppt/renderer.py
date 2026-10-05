from __future__ import annotations

from pptx import Presentation

from media_automation.bible import BibleProvider
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)

from .base import (
    add_blank_slide,
    add_centered_text_slide,
    add_sermon_title_slide,
)
from .scripture import (
    _display_bible_reference,
    add_scripture_passage_slides,
)

class MissingRenderDependencyError(
    RuntimeError
):
    pass


def render_block(
    prs: Presentation,
    block: WorshipBlock,
    *,
    bible_provider: BibleProvider | None = None,
):
    if block.kind == BlockKind.BLANK:
        return add_blank_slide(
            prs
        )

    if block.kind == BlockKind.PRAYER:
        person = block.value.person

        return add_centered_text_slide(
            prs,
            f"기 도 : {person}",
            font_size=34,
        )

    if block.kind == BlockKind.CHURCH_NEWS:
        return add_centered_text_slide(
            prs,
            "교회 소식",
            font_size=34,
        )

    if block.kind == BlockKind.SERMON_TITLE:
        return add_sermon_title_slide(
            prs,
            block.value.title,
            _display_bible_reference(
                block.value.scripture_reference
            ),
        )

    if block.kind == BlockKind.SCRIPTURE:
        if bible_provider is None:
            raise MissingRenderDependencyError(
                "SCRIPTURE 블록을 렌더링하려면 "
                "BibleProvider가 필요합니다."
            )

        passage = bible_provider.get_passage(
            block.value.reference
        )

        return add_scripture_passage_slides(
            prs,
            passage,
        )

    raise ValueError(
        f"renderer가 지원하지 않는 블록입니다: "
        f"{block.kind}"
    )