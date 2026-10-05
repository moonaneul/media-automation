from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True, slots=True)
class CompletedWorshipReference:
    leader: str
    praise_first: str
    praise_second: str
    hymn: str
    prayer_first: str
    prayer_second: str
    offering_hymn: str
    offering_prayer_first: str
    offering_prayer_second: str
    scripture: str
    sermon_title: str
    decision_hymn: str
    closing_prayer: str


@dataclass(frozen=True, slots=True)
class CompletedServingWeek:
    first_prayer: str
    first_offering_prayer: str
    second_prayer: str
    second_offering_prayer: str
    dishwashing: str
    wednesday_prayer: str


@dataclass(frozen=True, slots=True)
class CompletedCellGroupReference:
    scripture: str
    title: str
    questions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CompletedBulletinReference:
    worship: CompletedWorshipReference
    this_week: CompletedServingWeek
    next_week: CompletedServingWeek
    cell_group: CompletedCellGroupReference
    church_news: tuple[str, ...]
    monthly_schedule: tuple[str, ...]
    bulletin_number: str
    date_text: str


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _clean_lines(text: str) -> list[str]:
    result = []

    for raw in text.splitlines():
        line = raw.strip()

        if not line:
            continue

        # HWP 표의 구분선은 데이터가 아니다.
        if re.fullmatch(r"-+", line):
            continue

        result.append(line)

    return result


def _find(
    lines: list[str],
    target: str,
    *,
    start: int = 0,
) -> int:
    wanted = _norm(target)

    for index in range(start, len(lines)):
        if _norm(lines[index]) == wanted:
            return index

    raise ValueError(
        f"완성 주보에서 항목을 찾지 못했습니다: {target}"
    )


def _section(
    lines: list[str],
    start: str,
    end: str,
) -> list[str]:
    start_index = _find(lines, start) + 1
    end_index = _find(
        lines,
        end,
        start=start_index,
    )

    return lines[start_index:end_index]


def _first_data_line(
    values: list[str],
    *,
    ignored: tuple[str, ...] = (),
) -> str:
    ignored_norm = {
        _norm(value)
        for value in ignored
    }

    for value in values:
        if _norm(value) not in ignored_norm:
            return value

    raise ValueError(
        "완성 주보 구간에서 값을 찾지 못했습니다."
    )


def _service_pair(
    values: list[str],
) -> tuple[str, str]:
    first = None
    second = None

    index = 0

    while index < len(values):
        line = values[index]

        match = re.match(
            r"^1\s*부\s*(.*)$",
            line,
        )

        if match:
            inline = match.group(1).strip()

            if inline:
                first = inline
            elif index + 1 < len(values):
                first = values[index + 1]

            index += 1
            continue

        match = re.match(
            r"^2\s*부\s*(.*)$",
            line,
        )

        if match:
            inline = match.group(1).strip()

            if inline:
                second = inline
            elif index + 1 < len(values):
                second = values[index + 1]

            index += 1
            continue

        index += 1

    if first is None or second is None:
        raise ValueError(
            "1부/2부 값을 모두 찾지 못했습니다."
        )

    return first, second


def _parse_serving_week(
    values: list[str],
) -> CompletedServingWeek:
    first_index = _find(
        values,
        "1부",
    )
    second_index = _find(
        values,
        "2부",
        start=first_index + 1,
    )

    first_values = values[
        first_index + 1:
        second_index
    ]

    second_values = values[
        second_index + 1:
    ]

    if (
        len(first_values) != 4
        or len(second_values) != 2
    ):
        raise ValueError(
            "완성 주보 섬김표 값 개수가 예상과 다릅니다."
        )

    return CompletedServingWeek(
        first_prayer=first_values[0],
        first_offering_prayer=first_values[1],
        second_prayer=second_values[0],
        second_offering_prayer=second_values[1],
        dishwashing=first_values[2],
        wednesday_prayer=first_values[3],
    )


def parse_completed_bulletin_text(
    text: str,
) -> CompletedBulletinReference:
    lines = _clean_lines(text)

    # -------------------------
    # 오전 예배 순서
    # -------------------------

    leader_section = _section(
        lines,
        "인 도 :",
        "경배와 찬양",
    )

    leader = _first_data_line(
        leader_section
    )

    praise_section = _section(
        lines,
        "경배와 찬양",
        "예배로의 부르심",
    )

    praise_first, praise_second = (
        _service_pair(
            praise_section
        )
    )

    hymn = _first_data_line(
        _section(
            lines,
            "찬 송",
            "기 도",
        ),
        ignored=("다 같 이",),
    )

    prayer_first, prayer_second = (
        _service_pair(
            _section(
                lines,
                "기 도",
                "환 영",
            )
        )
    )

    offering_hymn = _first_data_line(
        _section(
            lines,
            "봉 헌 찬 송",
            "봉 헌 기 도",
        ),
        ignored=("다 같 이",),
    )

    (
        offering_prayer_first,
        offering_prayer_second,
    ) = _service_pair(
        _section(
            lines,
            "봉 헌 기 도",
            "성 경 봉 독",
        )
    )

    scripture = _first_data_line(
        _section(
            lines,
            "성 경 봉 독",
            "말 씀 선 포",
        ),
        ignored=("인 도 자",),
    )

    sermon_title = _first_data_line(
        _section(
            lines,
            "말 씀 선 포",
            "결 단 찬 송",
        ),
        ignored=("이은철 목사",),
    )

    decision_hymn = _first_data_line(
        _section(
            lines,
            "결 단 찬 송",
            "폐 회 기 도",
        ),
        ignored=("인 도 자",),
    )

    closing_prayer = _first_data_line(
        _section(
            lines,
            "폐 회 기 도",
            "* 헌금은 예배 전에 헌금함에 넣어 주시기 바랍니다.",
        )
    )

    # -------------------------
    # 섬김표
    # -------------------------

    serving_start = _find(
        lines,
        "<예배 / 섬김>",
    )

    this_index = _find(
        lines,
        "이 번 주",
        start=serving_start,
    )

    next_index = _find(
        lines,
        "다 음 주",
        start=this_index + 1,
    )

    serving_end = _find(
        lines,
        "주 일 오 전",
        start=next_index + 1,
    )

    this_week = _parse_serving_week(
        lines[
            this_index + 1:
            next_index
        ]
    )

    next_week = _parse_serving_week(
        lines[
            next_index + 1:
            serving_end
        ]
    )

    # -------------------------
    # 목장 말씀 나누기
    # -------------------------

    cell_start = _find(
        lines,
        "* 목장 말씀 나누기",
    )

    cell_end = _find(
        lines,
        "<교 회 소 식>",
        start=cell_start + 1,
    )

    cell_lines = lines[
        cell_start + 1:
        cell_end
    ]

    header = next(
        value
        for value in cell_lines
        if (
            value.startswith("<")
            and value.endswith(">")
            and "/" in value
        )
    )

    header_text = header[1:-1]
    scripture_cell, _, title_cell = (
        header_text.partition("/")
    )

    questions = tuple(
        re.sub(
            r"^\d+\.\s*",
            "",
            line,
        )
        for line in cell_lines
        if re.match(
            r"^\d+\.",
            line,
        )
    )

    if len(questions) != 4:
        raise ValueError(
            "완성 주보 목장 질문이 4개가 아닙니다."
        )

    # -------------------------
    # 교회 소식
    # -------------------------

    news_lines = _section(
        lines,
        "<교 회 소 식>",
        "<9월 사역 일정>",
    )

    church_news = tuple(
        re.sub(
            r"^\d+\.\s*",
            "",
            line,
        )
        for line in news_lines
        if re.match(
            r"^\d+\.",
            line,
        )
    )

    # -------------------------
    # 월간 일정
    # -------------------------

    schedule_lines = _section(
        lines,
        "<9월 사역 일정>",
        "<예배 / 모임 안내>",
    )

    monthly_schedule = tuple(
        line
        for line in schedule_lines
        if re.match(
            r"^\d{1,2}/\d{1,2}",
            line,
        )
    )

    # -------------------------
    # 표지
    # -------------------------

    cover_pattern = re.compile(
        r"^No\.\s*(\S+)\s+"
        r"(\d{4}년\s+\d+월\s+\d+일)$"
    )

    bulletin_number = None
    date_text = None

    for line in lines:
        match = cover_pattern.match(line)

        if match:
            bulletin_number = match.group(1)
            date_text = match.group(2)
            break

    if bulletin_number is None:
        raise ValueError(
            "완성 주보의 호수/날짜를 찾지 못했습니다."
        )

    return CompletedBulletinReference(
        worship=CompletedWorshipReference(
            leader=leader,
            praise_first=praise_first,
            praise_second=praise_second,
            hymn=hymn,
            prayer_first=prayer_first,
            prayer_second=prayer_second,
            offering_hymn=offering_hymn,
            offering_prayer_first=(
                offering_prayer_first
            ),
            offering_prayer_second=(
                offering_prayer_second
            ),
            scripture=scripture,
            sermon_title=sermon_title,
            decision_hymn=decision_hymn,
            closing_prayer=closing_prayer,
        ),
        this_week=this_week,
        next_week=next_week,
        cell_group=CompletedCellGroupReference(
            scripture=scripture_cell.strip(),
            title=title_cell.strip(),
            questions=questions,
        ),
        church_news=church_news,
        monthly_schedule=monthly_schedule,
        bulletin_number=bulletin_number,
        date_text=date_text,
    )
