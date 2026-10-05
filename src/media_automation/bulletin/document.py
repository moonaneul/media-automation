from __future__ import annotations

from dataclasses import dataclass

from media_automation.weekly_data.models import (
    SundayData,
    WeeklyStatus,
)


@dataclass(frozen=True, slots=True)
class BulletinCoverPage:
    bulletin_number: str | None
    date_text: str


@dataclass(frozen=True, slots=True)
class BulletinWorshipPage:
    leader: str | None = None
    praise_first: str | None = None
    praise_second: str | None = None
    preacher: str | None = None
    closing_prayer: str | None = None

    first_service_prayer_display: str | None = None
    second_service_prayer_display: str | None = None
    first_service_offering_prayer_display: str | None = None
    second_service_offering_prayer_display: str | None = None

    separate_hymn: str | None = None
    first_service_prayer: str | None = None
    second_service_prayer: str | None = None
    offering_hymn: str | None = None
    first_service_offering_prayer: str | None = None
    second_service_offering_prayer: str | None = None
    scripture: str | None = None
    sermon_title: str | None = None
    decision_hymn: str | None = None

    this_week_dishwashing: str | None = None
    this_week_wednesday_prayer: str | None = None

    next_week_first_service_prayer: str | None = None
    next_week_second_service_prayer: str | None = None
    next_week_first_service_offering_prayer: str | None = None
    next_week_second_service_offering_prayer: str | None = None
    next_week_dishwashing: str | None = None
    next_week_wednesday_prayer: str | None = None

    afternoon_service: str | None = None


@dataclass(frozen=True, slots=True)
class BulletinCellGroupPage:
    scripture: str | None = None
    title: str | None = None
    questions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BulletinNewsPage:
    church_news: tuple[str, ...]
    monthly_schedule: tuple[
        tuple[str, str],
        ...,
    ]
    schedule_month: int | None = None


@dataclass(frozen=True, slots=True)
class BulletinDocument:
    cover: BulletinCoverPage
    worship: BulletinWorshipPage
    cell_group: BulletinCellGroupPage
    news: BulletinNewsPage


def _person(field) -> str | None:
    if field.status == WeeklyStatus.VALUE:
        return field.person

    return None


def _person_display(field) -> str | None:
    if field.status != WeeklyStatus.VALUE:
        return None

    if field.title:
        return f"{field.person} {field.title}"

    return field.person


def _text(field) -> str | None:
    if field.status == WeeklyStatus.VALUE:
        return field.text

    return None


def _scripture(field) -> str | None:
    if field.status == WeeklyStatus.VALUE:
        return field.reference

    return None


def _song(field) -> str | None:
    if field.status != WeeklyStatus.VALUE:
        return None

    if field.hymn_number is not None:
        return f"{field.hymn_number}장"

    return field.title


def build_bulletin_document(
    sunday: SundayData,
) -> BulletinDocument:
    bulletin = sunday.bulletin
    serving = sunday.serving
    worship = sunday.worship

    number = None

    if (
        bulletin.number.status
        == WeeklyStatus.VALUE
    ):
        number = bulletin.number.value

    afternoon = None

    if (
        bulletin.afternoon_service.status
        == WeeklyStatus.VALUE
    ):
        afternoon = (
            bulletin.afternoon_service.title
        )

    cell_scripture = None
    cell_title = None
    questions: tuple[str, ...] = ()

    if (
        bulletin.cell_group.status
        == WeeklyStatus.VALUE
    ):
        cell_scripture = (
            bulletin.cell_group.scripture
        )
        cell_title = bulletin.cell_group.title
        questions = tuple(
            bulletin.cell_group.questions
            or []
        )

    church_news: tuple[str, ...] = ()

    if (
        bulletin.church_news.status
        == WeeklyStatus.VALUE
    ):
        church_news = tuple(
            item.text
            for item in (
                bulletin.church_news.items
                or []
            )
        )

    schedule: list[tuple[str, str]] = []

    if (
        bulletin.monthly_schedule.status
        == WeeklyStatus.VALUE
    ):
        for item in (
            bulletin.monthly_schedule.items
            or []
        ):
            if item.display_date:
                date_text = item.display_date
            elif item.date is not None:
                date_text = (
                    f"{item.date.month}/"
                    f"{item.date.day}"
                )
            else:
                date_text = ""

            schedule.append(
                (
                    date_text,
                    item.content,
                )
            )

    return BulletinDocument(
        cover=BulletinCoverPage(
            bulletin_number=number,
            date_text=(
                f"{sunday.date.year}년 "
                f"{sunday.date.month}월 "
                f"{sunday.date.day}일"
            ),
        ),
        worship=BulletinWorshipPage(
            leader=_person_display(
                worship.leader
            ),
            praise_first=_person_display(
                worship.praise_first
            ),
            praise_second=_person_display(
                worship.praise_second
            ),
            preacher=_person_display(
                worship.preacher
            ),
            closing_prayer=_person_display(
                worship.closing_prayer
            ),
            first_service_prayer_display=(
                _person_display(
                    serving.this_week
                    .first_service.prayer
                )
            ),
            second_service_prayer_display=(
                _person_display(
                    serving.this_week
                    .second_service.prayer
                )
            ),
            first_service_offering_prayer_display=(
                _person_display(
                    serving.this_week
                    .first_service.offering_prayer
                )
            ),
            second_service_offering_prayer_display=(
                _person_display(
                    serving.this_week
                    .second_service.offering_prayer
                )
            ),
            separate_hymn=_song(
                worship.separate_hymn
            ),
            first_service_prayer=_person(
                serving.this_week
                .first_service.prayer
            ),
            second_service_prayer=_person(
                serving.this_week
                .second_service.prayer
            ),
            offering_hymn=_song(
                worship.offering_hymn
            ),
            first_service_offering_prayer=(
                _person(
                    serving.this_week
                    .first_service
                    .offering_prayer
                )
            ),
            second_service_offering_prayer=(
                _person(
                    serving.this_week
                    .second_service
                    .offering_prayer
                )
            ),
            scripture=_scripture(
                worship.scripture
            ),
            sermon_title=_text(
                worship.sermon_title
            ),
            decision_hymn=_song(
                worship.decision_hymn
            ),
            this_week_dishwashing=_person(
                serving.this_week.dishwashing
            ),
            this_week_wednesday_prayer=(
                _person(
                    serving.this_week
                    .wednesday_prayer
                )
            ),
            next_week_first_service_prayer=_person(
                serving.next_week.first_service.prayer
            ),
            next_week_second_service_prayer=_person(
                serving.next_week.second_service.prayer
            ),
            next_week_first_service_offering_prayer=_person(
                serving.next_week.first_service.offering_prayer
            ),
            next_week_second_service_offering_prayer=_person(
                serving.next_week.second_service.offering_prayer
            ),
            next_week_dishwashing=_person(
                serving.next_week.dishwashing
            ),
            next_week_wednesday_prayer=(
                _person(
                    serving.next_week
                    .wednesday_prayer
                )
            ),
            afternoon_service=afternoon,
        ),
        cell_group=BulletinCellGroupPage(
            scripture=cell_scripture,
            title=cell_title,
            questions=questions,
        ),
        news=BulletinNewsPage(
            church_news=church_news,
            monthly_schedule=tuple(
                schedule
            ),
            schedule_month=sunday.date.month,
        ),
    )
