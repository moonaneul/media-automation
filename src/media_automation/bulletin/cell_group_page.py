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

    if page.questions and len(page.questions) != 4:
        raise ValueError("목장 말씀 나누기 질문은 4개여야 합니다.")

    canvas.saveState()
    canvas.setLineWidth(0.9)
    canvas.roundRect(x + 6 * mm, y + 7 * mm, width - 12 * mm,
                     height - 14 * mm, 7 * mm)
    left = x + 10 * mm
    right = x + width - 10 * mm
    canvas.setFillColorRGB(0, 0, 0)
    canvas.setFont(FONT_BOLD, 10.5)
    canvas.drawString(left, y + height - 19 * mm, "* 목장 말씀 나누기")
    canvas.setFillColorRGB(0, 0, 0)
    heading = " / ".join(value for value in (page.scripture, page.title) if value)
    heading_lines = wrap_text(f"<{heading}>" if heading else "",
                              font_name=FONT_REGULAR, font_size=9,
                              max_width=right - left)
    heading_cursor = y + height - 29 * mm
    canvas.setFont(FONT_REGULAR, 9)
    for line in heading_lines:
        canvas.drawRightString(right, heading_cursor, line)
        heading_cursor -= 4.5 * mm

    question_top = heading_cursor - 7 * mm
    bottom = y + 15 * mm
    slot_height = (question_top - bottom) / 4
    for index, question in enumerate(page.questions):
        cursor = question_top - index * slot_height
        lines = wrap_text(question, font_name=FONT_REGULAR, font_size=9.2,
                          max_width=right - left - 6 * mm)
        # Keep at least 12 mm for handwritten notes after each question.
        if len(lines) * 5 * mm + 12 * mm > slot_height:
            raise ValueError("목장 말씀 나누기 질문이 페이지 영역을 넘습니다.")
        canvas.setFont(FONT_REGULAR, 9.2)
        canvas.drawString(left, cursor, f"{index + 1}.")
        for line in lines:
            canvas.drawString(left + 6 * mm, cursor, line)
            cursor -= 5 * mm
    canvas.restoreState()
