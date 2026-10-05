from __future__ import annotations

from dataclasses import dataclass

from media_automation.bulletin.transfer import (
    BulletinTransferData,
    TransferServing,
    TransferTextField,
)
from media_automation.weekly_data.models import (
    AfternoonService,
    CellGroup,
    ChurchNews,
    FirstService,
    MonthlySchedule,
    NewsItem,
    PersonField,
    ScheduleItem,
    ScriptureField,
    SecondService,
    Serving,
    SundayData,
    WeekServing,
    WeeklyStatus,
)


@dataclass(frozen=True, slots=True)
class BulletinMergeResult:
    sunday: SundayData

    # 전달 주보의 "찬양 : ..."은
    # 아직 예배 순서에 임의 매핑하지 않는다.
    praise_raw: TransferTextField


def _person(
    value: str,
    *,
    base: PersonField | None = None,
) -> PersonField:
    # 같은 사람이라면 SundayData에 있던 직분 표시는 유지.
    # 사람이 바뀌었으면 이전 사람의 직분을 승계하지 않는다.
    title = None

    if (
        base is not None
        and base.status == WeeklyStatus.VALUE
        and base.person == value
    ):
        title = base.title

    return PersonField(
        status=WeeklyStatus.VALUE,
        person=value,
        title=title,
    )


def _merge_additional_scripture(
    base: ScriptureField,
    transfer: TransferTextField,
) -> ScriptureField:
    if transfer.status == WeeklyStatus.UNSET:
        return base

    if transfer.status == WeeklyStatus.NONE:
        return ScriptureField(
            status=WeeklyStatus.NONE,
        )

    return ScriptureField(
        status=WeeklyStatus.VALUE,
        reference=transfer.value,
    )


def _merge_serving(
    base: Serving,
    transfer: TransferServing,
) -> Serving:
    if transfer.status == WeeklyStatus.UNSET:
        return base

    if (
        transfer.status != WeeklyStatus.VALUE
        or transfer.this_week is None
        or transfer.next_week is None
    ):
        raise ValueError(
            "예배/섬김 전달자료가 VALUE이면 "
            "이번 주와 다음 주 값이 모두 필요합니다."
        )

    def convert_week(
        source,
        base_week: WeekServing,
    ) -> WeekServing:
        return WeekServing(
            first_service=FirstService(
                prayer=_person(
                    source.first_service_prayer,
                    base=base_week.first_service.prayer,
                ),
                offering_prayer=_person(
                    source.first_service_offering_prayer,
                    base=(
                        base_week.first_service
                        .offering_prayer
                    ),
                ),
            ),
            second_service=SecondService(
                prayer=_person(
                    source.second_service_prayer,
                    base=base_week.second_service.prayer,
                ),
                offering_prayer=_person(
                    source.second_service_offering_prayer,
                    base=(
                        base_week.second_service
                        .offering_prayer
                    ),
                ),
            ),
            dishwashing=_person(
                source.dishwashing,
                base=base_week.dishwashing,
            ),
            wednesday_prayer=_person(
                source.wednesday_prayer,
                base=base_week.wednesday_prayer,
            ),
        )

    return Serving(
        this_week=convert_week(
            transfer.this_week,
            base.this_week,
        ),
        next_week=convert_week(
            transfer.next_week,
            base.next_week,
        ),
    )


def _merge_afternoon_service(
    base: AfternoonService,
    transfer: TransferTextField,
) -> AfternoonService:
    if transfer.status == WeeklyStatus.UNSET:
        return base

    if transfer.status == WeeklyStatus.NONE:
        return AfternoonService(
            status=WeeklyStatus.NONE,
        )

    # 전달 주보에서 제목만 수정한 경우
    # 같은 주 SundayData에 있던 description은 유지한다.
    return AfternoonService(
        status=WeeklyStatus.VALUE,
        title=transfer.value,
        description=base.description,
    )


def _merge_church_news(
    base: ChurchNews,
    transfer,
) -> ChurchNews:
    if transfer.status == WeeklyStatus.UNSET:
        return base

    if transfer.status == WeeklyStatus.NONE:
        return ChurchNews(
            status=WeeklyStatus.NONE,
        )

    return ChurchNews(
        status=WeeklyStatus.VALUE,
        items=[
            NewsItem(text=item)
            for item in transfer.items
        ],
    )


def _merge_monthly_schedule(
    base: MonthlySchedule,
    transfer,
) -> MonthlySchedule:
    if transfer.status == WeeklyStatus.UNSET:
        return base

    if transfer.status == WeeklyStatus.NONE:
        return MonthlySchedule(
            status=WeeklyStatus.NONE,
        )

    return MonthlySchedule(
        status=WeeklyStatus.VALUE,
        items=[
            ScheduleItem(
                display_date=item.display_date,
                content=item.content,
            )
            for item in transfer.items
        ],
    )


def _merge_cell_group(
    base: CellGroup,
    transfer,
) -> CellGroup:
    if transfer.status == WeeklyStatus.UNSET:
        return base

    if transfer.status == WeeklyStatus.NONE:
        return CellGroup(
            status=WeeklyStatus.NONE,
        )

    return CellGroup(
        status=WeeklyStatus.VALUE,
        scripture=transfer.scripture,
        title=transfer.title,
        questions=list(
            transfer.questions
        ),
    )


def merge_bulletin_transfer(
    sunday: SundayData,
    transfer: BulletinTransferData,
) -> BulletinMergeResult:
    if sunday.date != transfer.date:
        raise ValueError(
            "주일예배 안내와 전달 주보의 날짜가 "
            "다릅니다: "
            f"{sunday.date} != {transfer.date}"
        )

    worship = sunday.worship.model_copy(
        update={
            "additional_scripture":
                _merge_additional_scripture(
                    sunday.worship.additional_scripture,
                    transfer.additional_scripture,
                ),
        }
    )

    serving = _merge_serving(
        sunday.serving,
        transfer.serving,
    )

    bulletin = sunday.bulletin.model_copy(
        update={
            "afternoon_service":
                _merge_afternoon_service(
                    sunday.bulletin.afternoon_service,
                    transfer.afternoon_service,
                ),
            "church_news":
                _merge_church_news(
                    sunday.bulletin.church_news,
                    transfer.church_news,
                ),
            "monthly_schedule":
                _merge_monthly_schedule(
                    sunday.bulletin.monthly_schedule,
                    transfer.monthly_schedule,
                ),
            "cell_group":
                _merge_cell_group(
                    sunday.bulletin.cell_group,
                    transfer.cell_group,
                ),
        }
    )

    merged = sunday.model_copy(
        update={
            "worship": worship,
            "serving": serving,
            "bulletin": bulletin,
        }
    )

    return BulletinMergeResult(
        sunday=merged,
        praise_raw=transfer.praise_raw,
    )
