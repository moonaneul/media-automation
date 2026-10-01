from __future__ import annotations

from typing import Any

from media_automation.weekly_data.models import (
    WednesdayData,
    WeeklyStatus,
)

from .blocks import BlockKind, WorshipBlock


class IncompletePlanError(ValueError):
    """
    아직 UNSET인 Weekly Data 때문에
    예배 순서를 확정할 수 없을 때 발생한다.
    """


def _make_optional_block(
    *,
    field: Any,
    key: str,
    kind: BlockKind,
) -> WorshipBlock | None:
    """
    Weekly Status에 따라 블록 생성 여부를 결정한다.

    VALUE -> 블록 생성
    NONE  -> 이번 주에 없는 순서이므로 생성하지 않음
    UNSET -> 아직 확정되지 않았으므로 Plan 생성 중단
    """

    if field.status == WeeklyStatus.UNSET:
        raise IncompletePlanError(
            f"{key}가 아직 UNSET 상태입니다."
        )

    if field.status == WeeklyStatus.NONE:
        return None

    return WorshipBlock(
        kind=kind,
        key=key,
        value=field,
    )


def _insert_transition_blanks(
    blocks: list[WorshipBlock],
) -> list[WorshipBlock]:
    """
    주요 예배 순서 사이에 빈 화면 한 장을 삽입한다.

    같은 성경 본문의 절 사이 빈 화면은 여기서 만들지 않는다.
    Scripture 블록은 이후 PPT 생성 단계에서 절별 화면으로 확장한다.
    """

    if not blocks:
        return []

    result: list[WorshipBlock] = [blocks[0]]

    for previous, current in zip(blocks, blocks[1:]):
        result.append(
            WorshipBlock(
                kind=BlockKind.BLANK,
                key=f"transition:{previous.key}->{current.key}",
            )
        )
        result.append(current)

    return result


def build_wednesday_plan(
    data: WednesdayData,
) -> list[WorshipBlock]:
    """
    수요예배 Weekly Data를 실제 예배 순서 블록으로 변환한다.

    기본 흐름:

    예배 전 안내
    → 시작 찬양 3곡
    → 기도
    → 추가 찬양
    → 성경 봉독
    → 설교 제목
    → 추가 말씀
    → 결단 찬송

    NONE인 항목은 생략한다.
    UNSET이 하나라도 있으면 아직 순서를 확정하지 않는다.
    """

    content_blocks: list[WorshipBlock] = []

    # 시작 찬양 3곡
    for index, song in enumerate(
        data.opening_songs,
        start=1,
    ):
        block = _make_optional_block(
            field=song,
            key=f"opening_songs[{index - 1}]",
            kind=BlockKind.SONG,
        )

        if block is not None:
            content_blocks.append(block)

    # 기도
    block = _make_optional_block(
        field=data.prayer,
        key="prayer",
        kind=BlockKind.PRAYER,
    )
    if block is not None:
        content_blocks.append(block)

    # 추가 찬양
    block = _make_optional_block(
        field=data.additional_song,
        key="additional_song",
        kind=BlockKind.SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 성경 봉독
    block = _make_optional_block(
        field=data.scripture,
        key="scripture",
        kind=BlockKind.SCRIPTURE,
    )
    if block is not None:
        content_blocks.append(block)

    # 설교 제목
    block = _make_optional_block(
        field=data.sermon_title,
        key="sermon_title",
        kind=BlockKind.SERMON_TITLE,
    )
    if block is not None:
        content_blocks.append(block)

    # 추가 말씀
    block = _make_optional_block(
        field=data.additional_scripture,
        key="additional_scripture",
        kind=BlockKind.SCRIPTURE,
    )
    if block is not None:
        content_blocks.append(block)

    # 결단 찬송
    block = _make_optional_block(
        field=data.decision_hymn,
        key="decision_hymn",
        kind=BlockKind.SONG,
    )
    if block is not None:
        content_blocks.append(block)

    plan = [
        WorshipBlock(
            kind=BlockKind.PRE_SERVICE,
            key="pre_service",
        )
    ]

    # 현재 기준으로 예배 전 안내와 첫 찬양 사이에는
    # 별도의 blank를 자동 삽입하지 않는다.
    plan.extend(
        _insert_transition_blanks(content_blocks)
    )

    return plan