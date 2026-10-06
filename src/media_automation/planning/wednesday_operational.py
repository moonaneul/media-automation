from __future__ import annotations

from media_automation.weekly_data.models import WednesdayData

from .blocks import BlockKind, WorshipBlock
from .planner import build_wednesday_plan


def build_wednesday_operational_plan(
    data: WednesdayData,
) -> list[WorshipBlock]:
    """
    기존 Wednesday planning 규칙을 사용하되,
    실제 수요예배 운영 자료에서 반복 확인된
    예배 전 안내 -> 첫 찬양 사이 빈 화면 1장을 보존한다.

    과거 주차의 내용 자체를 승계하지 않고,
    이번 주 Weekly Data에서 만든 블록만 사용한다.
    """

    plan = list(
        build_wednesday_plan(data)
    )

    if len(plan) < 2:
        return plan

    first = plan[0]
    second = plan[1]

    if first.kind != BlockKind.PRE_SERVICE:
        return plan

    if second.kind == BlockKind.BLANK:
        return plan

    plan.insert(
        1,
        WorshipBlock(
            kind=BlockKind.BLANK,
            key=(
                "transition:pre_service->"
                f"{second.key}"
            ),
        ),
    )

    return plan
