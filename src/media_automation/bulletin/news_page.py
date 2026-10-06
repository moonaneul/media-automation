from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from media_automation.bulletin.cell_group_page import (
    wrap_text,
)
from media_automation.bulletin.cover import (
    FONT_BOLD,
    FONT_REGULAR,
    register_korean_fonts,
)
from media_automation.bulletin.document import (
    BulletinNewsPage,
)


@dataclass(frozen=True, slots=True)
class BulletinNewsStatic:
    meetings: tuple[
        tuple[str, str],
        ...,
    ] = (
        (
            "주일 오전 예배",
            "주일 오전 9시, 11시",
        ),
        (
            "주일 오후 예배",
            "주일 오후 1시 30분",
        ),
        (
            "유초등부 예배",
            "주일 오전 11시",
        ),
        (
            "학생부 예배",
            "주일 오전 9시",
        ),
        (
            "청년 예배",
            "토요일 오후 3시",
        ),
        (
            "수요 예배",
            "수요일 오후 7시 30분",
        ),
        (
            "새벽 기도",
            "화~금 오전 5시 30분",
        ),
        (
            "금요 기도회",
            "금요일 오후 9시",
        ),
        (
            "어머니 기도회",
            "목요일 오전 11시",
        ),
        (
            "장년 제자 훈련반",
            "수요일 오후 8시 40분",
        ),
    )

    mission: str = (
        "우리는 가서 제자를 삼아 가르쳐 "
        "지키게 하라는 주님의 지상명령에 "
        "순종하여 성령의 능력으로 민족의 "
        "복음화와 세계선교에 밀알이 된다."
    )

    core_values: tuple[str, ...] = (
        "예배의 감동이 넘치는 교회",
        "다음 세대를 준비하는 교회",
        "세계 선교에 동참하는 교회",
        "제자들이 재생산되는 교회",
        "하늘빛기쁨으로 행복한 교회",
        "가정을 말씀으로 세우는 교회",
    )

    joy_meaning: str = (
        "하늘빛 기쁨의 의미는 "
        "‘상황과 무관하게 그리스도로 인하여 "
        "기뻐하는 그리스도인의 기쁨’을 말합니다."
    )


def _section_title(
    canvas: Canvas,
    *,
    text: str,
    x: float,
    y: float,
    width: float,
) -> float:
    canvas.setFont(
        FONT_BOLD,
        9.5,
    )

    canvas.drawString(
        x,
        y,
        text,
    )

    canvas.line(
        x,
        y - 1.5 * mm,
        x + width,
        y - 1.5 * mm,
    )

    return y - 7.2 * mm


def _draw_wrapped(
    canvas: Canvas,
    *,
    text: str,
    x: float,
    y: float,
    max_width: float,
    font_size: float,
    line_height: float,
    bottom: float,
) -> float:
    lines = wrap_text(
        text,
        font_name=FONT_REGULAR,
        font_size=font_size,
        max_width=max_width,
    )

    canvas.setFont(
        FONT_REGULAR,
        font_size,
    )

    cursor = y

    for line in lines:
        if cursor < bottom:
            raise ValueError(
                "주보 4쪽 내용이 페이지 영역을 넘습니다."
            )

        canvas.drawString(
            x,
            cursor,
            line,
        )

        cursor -= line_height

    return cursor


def draw_news_page(
    canvas: Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    page: BulletinNewsPage,
    static: BulletinNewsStatic | None = None,
) -> None:
    register_korean_fonts()

    if static is None:
        static = BulletinNewsStatic()

    margin_x = 9 * mm
    margin_top = 10 * mm
    margin_bottom = 8 * mm

    left = x + margin_x
    right = x + width - margin_x
    content_width = right - left
    bottom = y + margin_bottom

    cursor = (
        y + height - margin_top
    )

    # --------------------------------
    # 교회 소식
    # --------------------------------

    cursor = _section_title(
        canvas,
        text="교 회 소 식",
        x=left,
        y=cursor,
        width=content_width,
    )

    for index, item in enumerate(
        page.church_news,
        start=1,
    ):
        cursor = _draw_wrapped(
            canvas,
            text=f"{index}. {item}",
            x=left,
            y=cursor,
            max_width=content_width,
            font_size=7.9,
            line_height=4.8 * mm,
            bottom=bottom,
        )

        cursor -= 2.1 * mm

    cursor -= 1.5 * mm

    # --------------------------------
    # 월간 사역 일정
    # --------------------------------

    if page.schedule_month is not None:
        schedule_title = (
            f"{page.schedule_month}월 사역 일정"
        )
    else:
        schedule_title = "사역 일정"

    cursor = _section_title(
        canvas,
        text=schedule_title,
        x=left,
        y=cursor,
        width=content_width,
    )

    for date_text, content in (
        page.monthly_schedule
    ):
        cursor = _draw_wrapped(
            canvas,
            text=(
                f"{date_text} : {content}"
            ),
            x=left,
            y=cursor,
            max_width=content_width,
            font_size=7.7,
            line_height=4.6 * mm,
            bottom=bottom,
        )

        cursor -= 1.6 * mm

    cursor -= 1.5 * mm

    # --------------------------------
    # 예배 / 모임 안내
    # --------------------------------

    cursor = _section_title(
        canvas,
        text="예배 / 모임 안내",
        x=left,
        y=cursor,
        width=content_width,
    )

    canvas.setFont(
        FONT_REGULAR,
        7.5,
    )

    label_width = 32 * mm

    for name, time_text in static.meetings:
        if cursor < bottom:
            raise ValueError(
                "주보 4쪽 예배/모임 안내가 "
                "페이지 영역을 넘습니다."
            )

        canvas.drawString(
            left,
            cursor,
            f"☞ {name}",
        )

        canvas.drawString(
            left + label_width,
            cursor,
            f"/ {time_text}",
        )

        cursor -= 4.8 * mm

    cursor -= 1.5 * mm

    # --------------------------------
    # 사명 선언문
    # --------------------------------

    cursor = _section_title(
        canvas,
        text="◇하늘빛기쁨교회 사명선언문◇",
        x=left,
        y=cursor,
        width=content_width,
    )

    cursor = _draw_wrapped(
        canvas,
        text=static.mission,
        x=left,
        y=cursor,
        max_width=content_width,
        font_size=7.4,
        line_height=4.3 * mm,
        bottom=bottom,
    )

    cursor -= 2 * mm

    # --------------------------------
    # 핵심 가치
    # --------------------------------

    cursor = _section_title(
        canvas,
        text="◇하늘빛기쁨교회 핵심가치◇",
        x=left,
        y=cursor,
        width=content_width,
    )

    canvas.setFont(
        FONT_REGULAR,
        7.3,
    )

    for index, value in enumerate(
        static.core_values,
        start=1,
    ):
        if cursor < bottom:
            raise ValueError(
                "주보 4쪽 핵심가치가 "
                "페이지 영역을 넘습니다."
            )

        canvas.drawString(
            left,
            cursor,
            f"{index}. {value}",
        )

        cursor -= 4.4 * mm

    cursor -= 1 * mm

    cursor = _draw_wrapped(
        canvas,
        text=f"* {static.joy_meaning}",
        x=left,
        y=cursor,
        max_width=content_width,
        font_size=6.9,
        line_height=4.0 * mm,
        bottom=bottom,
    )
