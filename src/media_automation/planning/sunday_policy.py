from __future__ import annotations

from media_automation.weekly_data.models import SundayData

from .blocks import BlockKind, WorshipBlock
from .planner import build_sunday_plan as build_historical_sunday_plan


SERMON_TO_SCRIPTURE_TRANSITION = (
    "transition:"
    "worship.sermon_title"
    "->worship.scripture"
)


def build_current_sunday_plan(
    data: SundayData,
) -> list[WorshipBlock]:
    """
    현재 교회 운영 규칙을 적용한 주일 오전 2부 Plan.

    과거 2026년 1월 자료에는 설교 제목과 성경 봉독 사이에
    빈 화면이 없는 사례가 있었지만, 현재 운영 규칙은 주요 순서가
    바뀔 때 빈 화면 한 장을 두는 것이다.

    과거 자료 분석용 planner는 그대로 보존하고, 실제 제작에서는
    이 policy를 사용한다.
    """

    plan = list(build_historical_sunday_plan(data))

    keys = [block.key for block in plan]

    if SERMON_TO_SCRIPTURE_TRANSITION in keys:
        return plan

    try:
        sermon_index = keys.index("worship.sermon_title")
        scripture_index = keys.index("worship.scripture")
    except ValueError:
        return plan

    if scripture_index != sermon_index + 1:
        return plan

    plan.insert(
        scripture_index,
        WorshipBlock(
            kind=BlockKind.BLANK,
            key=SERMON_TO_SCRIPTURE_TRANSITION,
        ),
    )

    return plan
