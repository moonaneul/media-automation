from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from media_automation.weekly_data.models import (
    WeeklyStatus,
)


@dataclass(frozen=True, slots=True)
class TransferTextField:
    status: WeeklyStatus
    value: str | None = None


@dataclass(frozen=True, slots=True)
class TransferListField:
    status: WeeklyStatus
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransferScheduleItem:
    display_date: str
    content: str


@dataclass(frozen=True, slots=True)
class TransferScheduleField:
    status: WeeklyStatus
    items: tuple[TransferScheduleItem, ...] = ()


@dataclass(frozen=True, slots=True)
class TransferCellGroup:
    status: WeeklyStatus
    scripture: str | None = None
    title: str | None = None
    questions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TransferServingWeek:
    first_service_prayer: str
    first_service_offering_prayer: str
    second_service_prayer: str
    second_service_offering_prayer: str
    dishwashing: str
    wednesday_prayer: str


@dataclass(frozen=True, slots=True)
class TransferServing:
    status: WeeklyStatus
    this_week: TransferServingWeek | None = None
    next_week: TransferServingWeek | None = None


@dataclass(frozen=True, slots=True)
class BulletinTransferData:
    date: date
    afternoon_service: TransferTextField
    praise_raw: TransferTextField
    additional_scripture: TransferTextField
    serving: TransferServing
    church_news: TransferListField
    monthly_schedule: TransferScheduleField
    cell_group: TransferCellGroup


def _clean_lines(text: str) -> list[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]


def _parse_date(
    lines: list[str],
    *,
    year: int,
) -> date:
    for line in lines:
        match = re.fullmatch(
            r"(\d{1,2})/(\d{1,2})",
            line,
        )

        if match:
            return date(
                year,
                int(match.group(1)),
                int(match.group(2)),
            )

    raise ValueError(
        "전달 주보에서 날짜를 찾을 수 없습니다."
    )


def _parse_colon_field(
    lines: list[str],
    prefix: str,
) -> TransferTextField:
    for line in lines:
        if not line.startswith(prefix):
            continue

        _, _, value = line.partition(":")
        value = value.strip()

        if value:
            return TransferTextField(
                status=WeeklyStatus.VALUE,
                value=value,
            )

        return TransferTextField(
            status=WeeklyStatus.NONE,
        )

    return TransferTextField(
        status=WeeklyStatus.UNSET,
    )


def _parse_additional_scripture(
    lines: list[str],
) -> TransferTextField:
    marker = "설교 중 읽을 말씀"

    for line in lines:
        cleaned = line.lstrip("*").strip()

        if not cleaned.startswith(marker):
            continue

        value = cleaned[len(marker):]
        value = value.lstrip(" ☞:").strip()

        if value:
            return TransferTextField(
                status=WeeklyStatus.VALUE,
                value=value,
            )

        return TransferTextField(
            status=WeeklyStatus.NONE,
        )

    return TransferTextField(
        status=WeeklyStatus.UNSET,
    )


def _section_lines(
    lines: list[str],
    start_pattern: str,
    end_patterns: tuple[str, ...],
) -> list[str] | None:
    start_index = None

    for index, line in enumerate(lines):
        if re.fullmatch(start_pattern, line):
            start_index = index + 1
            break

    if start_index is None:
        return None

    result = []

    for line in lines[start_index:]:
        if any(
            re.fullmatch(pattern, line)
            for pattern in end_patterns
        ):
            break

        result.append(line)

    return result


def _parse_numbered_section(
    lines: list[str],
    start_pattern: str,
    end_patterns: tuple[str, ...],
) -> TransferListField:
    section = _section_lines(
        lines,
        start_pattern,
        end_patterns,
    )

    if section is None:
        return TransferListField(
            status=WeeklyStatus.UNSET,
        )

    items = []

    for line in section:
        match = re.match(
            r"^\d+\.\s*(.+)$",
            line,
        )

        if match:
            items.append(
                match.group(1).strip()
            )

    if not items:
        return TransferListField(
            status=WeeklyStatus.NONE,
        )

    return TransferListField(
        status=WeeklyStatus.VALUE,
        items=tuple(items),
    )


def _parse_schedule(
    lines: list[str],
) -> TransferScheduleField:
    section = _section_lines(
        lines,
        r"<\d+월 사역 일정>",
        (
            r"<목장 말씀 나누기>",
        ),
    )

    if section is None:
        return TransferScheduleField(
            status=WeeklyStatus.UNSET,
        )

    items = []

    for line in section:
        if not re.match(
            r"^\d{1,2}/\d{1,2}",
            line,
        ):
            continue

        display_date, separator, content = (
            line.partition(":")
        )

        if not separator:
            raise ValueError(
                "월간 일정은 "
                "'날짜 : 내용' 형식이어야 합니다: "
                f"{line}"
            )

        display_date = display_date.strip()
        content = content.strip()

        if not display_date or not content:
            raise ValueError(
                "월간 일정의 날짜 또는 내용이 "
                f"비어 있습니다: {line}"
            )

        items.append(
            TransferScheduleItem(
                display_date=display_date,
                content=content,
            )
        )

    if not items:
        return TransferScheduleField(
            status=WeeklyStatus.NONE,
        )

    return TransferScheduleField(
        status=WeeklyStatus.VALUE,
        items=tuple(items),
    )

def _normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _find_normalized(
    lines: list[str],
    target: str,
    *,
    start: int = 0,
) -> int | None:
    normalized_target = _normalize_label(
        target
    )

    for index in range(start, len(lines)):
        if (
            _normalize_label(lines[index])
            == normalized_target
        ):
            return index

    return None


def _parse_serving_week(
    lines: list[str],
    *,
    start: int,
    end: int,
) -> TransferServingWeek:
    first_index = _find_normalized(
        lines,
        "1부",
        start=start,
    )
    second_index = _find_normalized(
        lines,
        "2부",
        start=start,
    )

    if (
        first_index is None
        or second_index is None
        or first_index >= end
        or second_index >= end
        or second_index <= first_index
    ):
        raise ValueError(
            "예배/섬김 표의 1부·2부 구조를 "
            "확인할 수 없습니다."
        )

    first_values = [
        value
        for value in lines[
            first_index + 1:
            second_index
        ]
        if value
    ]

    second_values = [
        value
        for value in lines[
            second_index + 1:
            end
        ]
        if value
    ]

    # 전달 주보 표의 텍스트 추출 순서:
    #
    # 1부
    #   기도
    #   봉헌기도
    #   설거지
    #   수요예배 기도
    # 2부
    #   기도
    #   봉헌기도
    #
    # 값이 빠진 상태에서 위치를 추정하지 않는다.
    if (
        len(first_values) != 4
        or len(second_values) != 2
    ):
        raise ValueError(
            "예배/섬김 표의 값 개수가 예상과 "
            "다릅니다. 빈 값을 임의 추정하지 않습니다."
        )

    return TransferServingWeek(
        first_service_prayer=(
            first_values[0]
        ),
        first_service_offering_prayer=(
            first_values[1]
        ),
        second_service_prayer=(
            second_values[0]
        ),
        second_service_offering_prayer=(
            second_values[1]
        ),
        dishwashing=first_values[2],
        wednesday_prayer=first_values[3],
    )


def _parse_serving(
    lines: list[str],
) -> TransferServing:
    section_index = None

    for index, line in enumerate(lines):
        normalized = _normalize_label(
            line.lstrip("*").strip()
        )

        if normalized in {
            "예배/섬김:",
            "예배/섬김",
        }:
            section_index = index
            break

    if section_index is None:
        return TransferServing(
            status=WeeklyStatus.UNSET,
        )

    this_index = _find_normalized(
        lines,
        "이번주",
        start=section_index + 1,
    )
    next_index = _find_normalized(
        lines,
        "다음주",
        start=section_index + 1,
    )

    if (
        this_index is None
        or next_index is None
        or next_index <= this_index
    ):
        raise ValueError(
            "예배/섬김 표에서 이번 주와 "
            "다음 주 구분을 찾을 수 없습니다."
        )

    end_index = len(lines)

    for index in range(
        next_index + 1,
        len(lines),
    ):
        line = lines[index]

        if (
            line.startswith("*1면")
            or line.startswith("<교회 소식>")
        ):
            end_index = index
            break

    this_week = _parse_serving_week(
        lines,
        start=this_index + 1,
        end=next_index,
    )

    next_week = _parse_serving_week(
        lines,
        start=next_index + 1,
        end=end_index,
    )

    return TransferServing(
        status=WeeklyStatus.VALUE,
        this_week=this_week,
        next_week=next_week,
    )


def _parse_cell_group(
    lines: list[str],
) -> TransferCellGroup:
    try:
        start = lines.index(
            "<목장 말씀 나누기>"
        )
    except ValueError:
        return TransferCellGroup(
            status=WeeklyStatus.UNSET,
        )

    section = lines[start + 1:]

    if not section:
        return TransferCellGroup(
            status=WeeklyStatus.NONE,
        )

    header = None
    header_index = None

    for index, line in enumerate(section):
        if (
            line.startswith("<")
            and line.endswith(">")
            and "/" in line
        ):
            header = line[1:-1].strip()
            header_index = index
            break

    if header is None:
        return TransferCellGroup(
            status=WeeklyStatus.NONE,
        )

    scripture, _, title = header.partition("/")

    questions = []

    for line in section[
        header_index + 1:
    ]:
        match = re.match(
            r"^\d+\.\s*(.+)$",
            line,
        )

        if match:
            questions.append(
                match.group(1).strip()
            )

    return TransferCellGroup(
        status=WeeklyStatus.VALUE,
        scripture=scripture.strip(),
        title=title.strip(),
        questions=tuple(questions),
    )


def parse_bulletin_transfer_text(
    text: str,
    *,
    year: int,
) -> BulletinTransferData:
    lines = _clean_lines(text)
    transfer_date = _parse_date(lines, year=year)
    for line in lines:
        schedule_heading = re.fullmatch(r"<(\d+)월 사역 일정>", line)
        if schedule_heading and int(schedule_heading.group(1)) != transfer_date.month:
            raise ValueError(
                "전달 주보 날짜와 월간 일정 제목의 월이 다릅니다: "
                f"{transfer_date} / {line}. 최신 전달 주보를 확인해주세요."
            )

    return BulletinTransferData(
        date=transfer_date,
        afternoon_service=(
            _parse_colon_field(
                lines,
                "cf) 오후 예배",
            )
        ),
        praise_raw=_parse_colon_field(
            lines,
            "찬양",
        ),
        additional_scripture=(
            _parse_additional_scripture(
                lines
            )
        ),
        serving=_parse_serving(
            lines
        ),
        church_news=(
            _parse_numbered_section(
                lines,
                r"<교회 소식>",
                (
                    r"<\d+월 사역 일정>",
                ),
            )
        ),
        monthly_schedule=(
            _parse_schedule(lines)
        ),
        cell_group=(
            _parse_cell_group(lines)
        ),
    )
