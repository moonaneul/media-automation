from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen.canvas import Canvas

from media_automation.bulletin.cover import (
    FONT_BOLD,
    FONT_REGULAR,
    register_korean_fonts,
)
from media_automation.bulletin.document import (
    BulletinCellGroupPage,
)


def wrap_text(
    text: str,
    *,
    font_name: str,
    font_size: float,
    max_width: float,
    char_space: float = 0,
) -> tuple[str, ...]:
    """
    한글을 포함한 문장을 실제 PDF 글자 폭 기준으로
    자동 줄바꿈한다.
    """
    text = text.strip()

    if not text:
        return ()

    lines: list[str] = []
    current = ""

    for char in text:
        candidate = current + char

        width = (
            pdfmetrics.stringWidth(
                candidate,
                font_name,
                font_size,
            )
            + max(
                0,
                len(candidate) - 1,
            ) * char_space
        )

        if (
            current
            and width > max_width
        ):
            # Do not leave punctuation alone on the next line.
            if char in ".,?!:;)]}":
                current += char
                lines.append(
                    current.rstrip()
                )
                current = ""
            else:
                lines.append(
                    current.rstrip()
                )
                current = char.lstrip()
        else:
            current = candidate

    if current:
        lines.append(
            current.rstrip()
        )

    return tuple(lines)


def draw_cell_group_page(
    canvas: Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    page: BulletinCellGroupPage,
) -> None:
    register_korean_fonts()

    margin_x = 12 * mm
    margin_top = 14 * mm
    margin_bottom = 12 * mm

    left = x + margin_x
    right = x + width - margin_x

    cursor = (
        y + height - margin_top
    )

    # -------------------------
    # 페이지 제목
    # -------------------------

    canvas.setFont(
        FONT_BOLD,
        14,
    )

    canvas.drawCentredString(
        x + width / 2,
        cursor,
        "목장 말씀 나누기",
    )

    cursor -= 9 * mm

    # -------------------------
    # 본문 / 제목
    # -------------------------

    if page.scripture:
        canvas.setFont(
            FONT_REGULAR,
            9,
        )
        canvas.drawCentredString(
            x + width / 2,
            cursor,
            page.scripture,
        )

        cursor -= 6 * mm

    if page.title:
        canvas.setFont(
            FONT_BOLD,
            13,
        )
        canvas.drawCentredString(
            x + width / 2,
            cursor,
            page.title,
        )

        cursor -= 10 * mm

    canvas.line(
        left,
        cursor + 3 * mm,
        right,
        cursor + 3 * mm,
    )

    # Keep the first question safely below the separator.
    cursor -= 5 * mm

    # -------------------------
    # 질문
    # -------------------------

    if (
        page.questions
        and len(page.questions) != 4
    ):
        raise ValueError(
            "목장 말씀 나누기 질문은 "
            "4개여야 합니다."
        )

    question_font_size = 9
    line_height = 6.3 * mm
    question_gap = 5.5 * mm
    number_width = 7 * mm

    text_width = (
        right
        - left
        - number_width
        - 4 * mm
    )

    question_char_space = 0

    for index, question in enumerate(
        page.questions,
        start=1,
    ):
        lines = wrap_text(
            question,
            font_name=FONT_REGULAR,
            font_size=question_font_size,
            max_width=text_width,
            char_space=question_char_space,
        )

        canvas.setFont(
            FONT_BOLD,
            question_font_size,
        )

        canvas.drawString(
            left,
            cursor,
            f"{index}.",
        )

        canvas.setFont(
            FONT_REGULAR,
            question_font_size,
        )

        line_cursor = cursor

        for line in lines:
            if (
                line_cursor
                < y + margin_bottom
            ):
                raise ValueError(
                    "목장 말씀 나누기 질문이 "
                    "페이지 영역을 넘습니다."
                )

            canvas.drawString(
                left + number_width,
                line_cursor,
                line,
            )

            line_cursor -= line_height

        cursor = (
            line_cursor
            - question_gap
        )
