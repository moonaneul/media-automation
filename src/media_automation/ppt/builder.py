from __future__ import annotations

from dataclasses import dataclass

from media_automation.bible import BibleProvider
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)

from .base import create_4x3_presentation
from .renderer import render_block


@dataclass(frozen=True, slots=True)
class UnsupportedPlanBlock:
    kind: BlockKind
    key: str


class UnsupportedPlanError(ValueError):
    def __init__(
        self,
        blocks: list[UnsupportedPlanBlock],
    ) -> None:
        self.blocks = blocks

        descriptions = ", ".join(
            f"{block.key}({block.kind.value})"
            for block in blocks
        )

        super().__init__(
            "지원하지 않는 Worship Plan 블록이 있습니다: "
            f"{descriptions}"
        )


SUPPORTED_BLOCK_KINDS = {
    BlockKind.BLANK,
    BlockKind.PRAYER,
    BlockKind.SERMON_TITLE,
    BlockKind.CHURCH_NEWS,
    BlockKind.SCRIPTURE,
}


def build_presentation_from_plan(
    plan: list[WorshipBlock],
    *,
    bible_provider: BibleProvider | None = None,
):
    unsupported = [
        UnsupportedPlanBlock(
            kind=block.kind,
            key=block.key,
        )
        for block in plan
        if block.kind not in SUPPORTED_BLOCK_KINDS
    ]

    if unsupported:
        raise UnsupportedPlanError(
            unsupported
        )

    prs = create_4x3_presentation()

    for block in plan:
        render_block(
            prs,
            block,
            bible_provider=bible_provider,
        )

    return prs