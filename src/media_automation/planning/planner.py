from __future__ import annotations

from typing import Any

from media_automation.weekly_data.models import (
    FridayZoomData,
    SundayData,
    WednesdayData,
    WeeklyStatus,
)

from .blocks import (
    BlockKind,
    SermonTitleContent,
    WorshipBlock,
)

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

def _make_sermon_title_block(
    *,
    title_field: Any,
    scripture_field: Any,
    key: str,
) -> WorshipBlock | None:
    if title_field.status == WeeklyStatus.UNSET:
        raise IncompletePlanError(
            f"{key}가 아직 UNSET 상태입니다."
        )

    if title_field.status == WeeklyStatus.NONE:
        return None

    if scripture_field.status == WeeklyStatus.UNSET:
        raise IncompletePlanError(
            f"{key}의 대표 본문이 아직 UNSET 상태입니다."
        )

    if scripture_field.status == WeeklyStatus.NONE:
        raise ValueError(
            f"{key}가 있는데 대표 본문이 NONE입니다."
        )

    return WorshipBlock(
        kind=BlockKind.SERMON_TITLE,
        key=key,
        value=SermonTitleContent(
            title=title_field.text,
            scripture_reference=(
                scripture_field.reference
            ),
        ),
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
    block = _make_sermon_title_block(
        title_field=data.sermon_title,
        scripture_field=data.scripture,
        key="sermon_title",
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

def build_sunday_plan(
    data: SundayData,
) -> list[WorshipBlock]:
    """
    Sunday Weekly Data를 주일 오전 2부 PPT 순서로 변환한다.

    기본 흐름:

    예배 전 안내
    → 시작 찬양 3곡
    → 별도 찬송
    → 기도
    → 교회 소식
    → 봉헌 찬송
    → 봉헌 기도
    → 특송
    → 설교 제목
    → 성경 봉독
    → 추가 말씀
    → 결단 찬송

    PPT에 필요한 담당자는
    serving.this_week.second_service에서 가져온다.

    church_news는 bulletin 데이터를 사용하지만,
    PPT에서는 상세 내용을 표시하지 않고
    '교회 소식' 단독 안내 화면 생성 여부에만 사용한다.
    """

    content_blocks: list[WorshipBlock] = []

    worship = data.worship
    second_service = data.serving.this_week.second_service

    # 시작 찬양 3곡
    for index, song in enumerate(worship.opening_songs):
        block = _make_optional_block(
            field=song,
            key=f"worship.opening_songs[{index}]",
            kind=BlockKind.SONG,
        )

        if block is not None:
            content_blocks.append(block)

    # 별도 찬송
    block = _make_optional_block(
        field=worship.separate_hymn,
        key="worship.separate_hymn",
        kind=BlockKind.SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 2부 기도
    block = _make_optional_block(
        field=second_service.prayer,
        key="serving.this_week.second_service.prayer",
        kind=BlockKind.PRAYER,
    )
    if block is not None:
        content_blocks.append(block)

    # 교회 소식
    block = _make_optional_block(
        field=data.bulletin.church_news,
        key="bulletin.church_news",
        kind=BlockKind.CHURCH_NEWS,
    )
    if block is not None:
        content_blocks.append(block)

    # 봉헌 찬송
    block = _make_optional_block(
        field=worship.offering_hymn,
        key="worship.offering_hymn",
        kind=BlockKind.SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 2부 봉헌기도
    block = _make_optional_block(
        field=second_service.offering_prayer,
        key="serving.this_week.second_service.offering_prayer",
        kind=BlockKind.PRAYER,
    )
    if block is not None:
        content_blocks.append(block)

    # 특송
    block = _make_optional_block(
        field=worship.special_song,
        key="worship.special_song",
        kind=BlockKind.SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 설교 제목
    block = _make_sermon_title_block(
        title_field=worship.sermon_title,
        scripture_field=worship.scripture,
        key="worship.sermon_title",
    )
    if block is not None:
        content_blocks.append(block)

    # 성경 봉독
    block = _make_optional_block(
        field=worship.scripture,
        key="worship.scripture",
        kind=BlockKind.SCRIPTURE,
    )
    if block is not None:
        content_blocks.append(block)

    # 추가 말씀
    block = _make_optional_block(
        field=worship.additional_scripture,
        key="worship.additional_scripture",
        kind=BlockKind.SCRIPTURE,
    )
    if block is not None:
        content_blocks.append(block)

    # 결단 찬송
    block = _make_optional_block(
        field=worship.decision_hymn,
        key="worship.decision_hymn",
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

    plan.extend(
        _insert_transition_blanks(content_blocks)
    )

    return plan

def build_friday_zoom_plan(
    data: FridayZoomData,
) -> list[WorshipBlock]:
    """
    금요기도회 Zoom Weekly Data를
    실제 예배 순서 블록으로 변환한다.

    기본 흐름:

    예배 준비
    → 찬양 2곡
    → 첫 기도 제목
    → 찬양
    → 본문 안내·봉독
    → 설교 제목
    → 추가 말씀
    → 응답 찬양
    → 말씀 관련 기도
    → 찬양
    → 공동체·중보기도
    → 개인 기도

    Zoom 찬양은 악보 찬양과 구분하여
    ZOOM_SONG 블록으로 만든다.
    """

    content_blocks: list[WorshipBlock] = []

    # 시작 찬양 2곡
    for index, song in enumerate(data.opening_songs):
        block = _make_optional_block(
            field=song,
            key=f"opening_songs[{index}]",
            kind=BlockKind.ZOOM_SONG,
        )

        if block is not None:
            content_blocks.append(block)

    # 첫 기도 제목
    block = _make_optional_block(
        field=data.first_prayer,
        key="first_prayer",
        kind=BlockKind.PRAYER_TOPICS,
    )
    if block is not None:
        content_blocks.append(block)

    # 기도 후 찬양
    block = _make_optional_block(
        field=data.song_after_prayer,
        key="song_after_prayer",
        kind=BlockKind.ZOOM_SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 본문 안내·봉독
    block = _make_optional_block(
        field=data.scripture,
        key="scripture",
        kind=BlockKind.SCRIPTURE,
    )
    if block is not None:
        content_blocks.append(block)

    # 설교 제목
    block = _make_sermon_title_block(
        title_field=data.sermon_title,
        scripture_field=data.scripture,
        key="sermon_title",
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

    # 응답 찬양
    block = _make_optional_block(
        field=data.response_song,
        key="response_song",
        kind=BlockKind.ZOOM_SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 말씀 관련 기도
    block = _make_optional_block(
        field=data.word_prayer,
        key="word_prayer",
        kind=BlockKind.PRAYER_TOPICS,
    )
    if block is not None:
        content_blocks.append(block)

    # 공동체·중보기도 전 찬양
    block = _make_optional_block(
        field=data.intercession_song,
        key="intercession_song",
        kind=BlockKind.ZOOM_SONG,
    )
    if block is not None:
        content_blocks.append(block)

    # 공동체·중보기도
    block = _make_optional_block(
        field=data.community_prayer,
        key="community_prayer",
        kind=BlockKind.PRAYER_TOPICS,
    )
    if block is not None:
        content_blocks.append(block)

    # 개인 기도
    block = _make_optional_block(
        field=data.personal_prayer,
        key="personal_prayer",
        kind=BlockKind.PERSONAL_PRAYER,
    )
    if block is not None:
        content_blocks.append(block)

    plan = [
        WorshipBlock(
            kind=BlockKind.PRE_SERVICE,
            key="pre_service",
        )
    ]

    plan.extend(
        _insert_transition_blanks(content_blocks)
    )

    return plan

