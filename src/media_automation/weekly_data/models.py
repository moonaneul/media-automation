from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class WeeklyStatus(str, Enum):
    UNSET = "UNSET"
    NONE = "NONE"
    VALUE = "VALUE"


class FileStatus(str, Enum):
    MISSING = "MISSING"
    AVAILABLE = "AVAILABLE"


class TechnicalCheck(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


class ChurchReview(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class UsagePermission(str, Enum):
    UNKNOWN = "UNKNOWN"
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"


class Song(StrictModel):
    status: WeeklyStatus
    title: str | None = None
    hymn_number: int | None = None
    verses: list[int] | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE:
            if not self.title:
                raise ValueError("VALUE인 찬양에는 title이 필요합니다.")
        else:
            if (
                self.title is not None
                or self.hymn_number is not None
                or self.verses is not None
            ):
                raise ValueError(
                    "UNSET/NONE인 찬양에는 실제 값을 넣을 수 없습니다."
                )

        return self


class PersonField(StrictModel):
    status: WeeklyStatus
    person: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.person:
            raise ValueError("VALUE인 담당자에는 person이 필요합니다.")

        if self.status != WeeklyStatus.VALUE and self.person is not None:
            raise ValueError(
                "UNSET/NONE인 담당자에는 person을 넣을 수 없습니다."
            )

        return self


class ScriptureField(StrictModel):
    status: WeeklyStatus
    reference: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.reference:
            raise ValueError("VALUE인 성경 본문에는 reference가 필요합니다.")

        if self.status != WeeklyStatus.VALUE and self.reference is not None:
            raise ValueError(
                "UNSET/NONE인 성경 본문에는 reference를 넣을 수 없습니다."
            )

        return self


class TextField(StrictModel):
    status: WeeklyStatus
    text: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.text:
            raise ValueError("VALUE인 항목에는 text가 필요합니다.")

        if self.status != WeeklyStatus.VALUE and self.text is not None:
            raise ValueError(
                "UNSET/NONE인 항목에는 text를 넣을 수 없습니다."
            )

        return self


class TopicsField(StrictModel):
    status: WeeklyStatus
    topics: list[str] | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE:
            if not self.topics:
                raise ValueError("VALUE인 기도 항목에는 topics가 필요합니다.")

            if any(not topic.strip() for topic in self.topics):
                raise ValueError("빈 기도 제목은 사용할 수 없습니다.")

        elif self.topics is not None:
            raise ValueError(
                "UNSET/NONE인 기도 항목에는 topics를 넣을 수 없습니다."
            )

        return self


class SequenceMarker(StrictModel):
    status: WeeklyStatus
    text: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status != WeeklyStatus.VALUE and self.text is not None:
            raise ValueError(
                "UNSET/NONE인 순서에는 text를 넣을 수 없습니다."
            )

        return self


class MediaField(StrictModel):
    status: WeeklyStatus
    file_status: FileStatus | None = None
    technical_check: TechnicalCheck | None = None
    church_review: ChurchReview | None = None
    usage_permission: UsagePermission | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        values = (
            self.file_status,
            self.technical_check,
            self.church_review,
            self.usage_permission,
        )

        if self.status == WeeklyStatus.VALUE:
            if any(value is None for value in values):
                raise ValueError(
                    "VALUE인 media에는 모든 검수 상태가 필요합니다."
                )
        elif any(value is not None for value in values):
            raise ValueError(
                "UNSET/NONE인 media에는 검수 상태를 넣을 수 없습니다."
            )

        return self


class ZoomSong(StrictModel):
    status: WeeklyStatus
    title: str | None = None
    media: MediaField | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE:
            if not self.title:
                raise ValueError("VALUE인 찬양에는 title이 필요합니다.")
            if self.media is None:
                raise ValueError("금요 Zoom 찬양에는 media가 필요합니다.")
        elif self.title is not None or self.media is not None:
            raise ValueError(
                "UNSET/NONE인 찬양에는 실제 값을 넣을 수 없습니다."
            )

        return self


# --------------------
# 수요
# --------------------

class WednesdayData(StrictModel):
    service: Literal["wednesday"]
    date: date

    opening_songs: list[Song] = Field(min_length=3, max_length=3)
    prayer: PersonField
    additional_song: Song
    scripture: ScriptureField
    sermon_title: TextField
    additional_scripture: ScriptureField
    decision_hymn: Song


# --------------------
# 주일
# --------------------

class FirstService(StrictModel):
    prayer: PersonField
    offering_prayer: PersonField


class SecondService(StrictModel):
    prayer: PersonField
    offering_prayer: PersonField


class WeekServing(StrictModel):
    first_service: FirstService
    second_service: SecondService
    dishwashing: PersonField
    wednesday_prayer: PersonField


class Serving(StrictModel):
    this_week: WeekServing
    next_week: WeekServing


class SundayWorship(StrictModel):
    opening_songs: list[Song] = Field(min_length=3, max_length=3)
    separate_hymn: Song
    offering_hymn: Song
    special_song: Song
    sermon_title: TextField
    scripture: ScriptureField
    additional_scripture: ScriptureField
    decision_hymn: Song


class BulletinNumber(StrictModel):
    status: WeeklyStatus
    value: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.value:
            raise ValueError("VALUE인 주보 호수에는 value가 필요합니다.")

        if self.status != WeeklyStatus.VALUE and self.value is not None:
            raise ValueError(
                "UNSET/NONE인 주보 호수에는 value를 넣을 수 없습니다."
            )

        return self


class NewsItem(StrictModel):
    text: str


class ChurchNews(StrictModel):
    status: WeeklyStatus
    items: list[NewsItem] | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.items:
            raise ValueError(
                "VALUE인 교회 소식에는 한 개 이상의 items가 필요합니다."
            )

        if self.status != WeeklyStatus.VALUE and self.items is not None:
            raise ValueError(
                "UNSET/NONE인 교회 소식에는 items를 넣을 수 없습니다."
            )

        return self


class AfternoonService(StrictModel):
    status: WeeklyStatus
    title: str | None = None
    description: str | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.title:
            raise ValueError("VALUE인 오후예배에는 title이 필요합니다.")

        if self.status != WeeklyStatus.VALUE:
            if self.title is not None or self.description is not None:
                raise ValueError(
                    "UNSET/NONE인 오후예배에는 내용을 넣을 수 없습니다."
                )

        return self


class ScheduleItem(StrictModel):
    date: date
    content: str


class MonthlySchedule(StrictModel):
    status: WeeklyStatus
    items: list[ScheduleItem] | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE and not self.items:
            raise ValueError(
                "VALUE인 월간 일정에는 한 개 이상의 items가 필요합니다."
            )

        if self.status != WeeklyStatus.VALUE and self.items is not None:
            raise ValueError(
                "UNSET/NONE인 월간 일정에는 items를 넣을 수 없습니다."
            )

        return self


class CellGroup(StrictModel):
    status: WeeklyStatus
    scripture: str | None = None
    title: str | None = None
    questions: list[str] | None = None

    @model_validator(mode="after")
    def validate_payload(self):
        if self.status == WeeklyStatus.VALUE:
            if not self.scripture:
                raise ValueError("목장 말씀에는 scripture가 필요합니다.")

            if not self.title:
                raise ValueError("목장 말씀에는 title이 필요합니다.")

            if self.questions is None or len(self.questions) != 4:
                raise ValueError("목장 질문은 정확히 4개여야 합니다.")

        elif (
            self.scripture is not None
            or self.title is not None
            or self.questions is not None
        ):
            raise ValueError(
                "UNSET/NONE인 목장 말씀에는 내용을 넣을 수 없습니다."
            )

        return self


class Bulletin(StrictModel):
    number: BulletinNumber
    church_news: ChurchNews
    afternoon_service: AfternoonService
    monthly_schedule: MonthlySchedule
    cell_group: CellGroup


class SundayData(StrictModel):
    service: Literal["sunday"]
    date: date
    worship: SundayWorship
    serving: Serving
    bulletin: Bulletin


# --------------------
# 금요 Zoom
# --------------------

class FridayZoomData(StrictModel):
    service: Literal["friday"]
    date: date
    mode: Literal["zoom"]

    opening_songs: list[ZoomSong] = Field(min_length=2, max_length=2)
    first_prayer: TopicsField
    song_after_prayer: ZoomSong

    scripture: ScriptureField
    sermon_title: TextField
    additional_scripture: ScriptureField

    response_song: ZoomSong
    word_prayer: TopicsField

    intercession_song: ZoomSong
    community_prayer: TopicsField

    personal_prayer: SequenceMarker


class FridayInPersonData(StrictModel):
    service: Literal["friday"]
    date: date
    mode: Literal["in_person"]


WeeklyData = (
    WednesdayData
    | SundayData
    | FridayZoomData
    | FridayInPersonData
)


def parse_weekly_data(data: dict[str, Any]) -> WeeklyData:
    service = data.get("service")

    if service == "wednesday":
        return WednesdayData.model_validate(data)

    if service == "sunday":
        return SundayData.model_validate(data)

    if service == "friday":
        mode = data.get("mode")

        if mode == "zoom":
            return FridayZoomData.model_validate(data)

        if mode == "in_person":
            return FridayInPersonData.model_validate(data)

        raise ValueError(
            "friday 데이터에는 mode: zoom 또는 mode: in_person이 필요합니다."
        )

    raise ValueError(
        "service는 wednesday, sunday, friday 중 하나여야 합니다."
    )