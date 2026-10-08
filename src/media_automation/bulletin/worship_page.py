from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from media_automation.bulletin.cover import (
    FONT_BOLD,
    FONT_REGULAR,
    register_korean_fonts,
)
from media_automation.bulletin.document import (
    BulletinWorshipPage,
)


def _join_services(
    first: str | None,
    second: str | None,
) -> str:
    values = []

    if first:
        values.append(f"1부 {first}")

    if second:
        values.append(f"2부 {second}")

    return " / ".join(values)


def build_worship_order_rows(
    page: BulletinWorshipPage,
) -> tuple[tuple[str, str], ...]:
    return (
        (
            "경배와 찬양",
            _join_services(
                page.praise_first,
                page.praise_second,
            ),
        ),
        (
            "예배로의 부르심",
            "인도자",
        ),
        (
            "찬 송",
            page.separate_hymn or "",
        ),
        (
            "기 도",
            _join_services(
                (
                    page.first_service_prayer_display
                    or page.first_service_prayer
                ),
                (
                    page.second_service_prayer_display
                    or page.second_service_prayer
                ),
            ),
        ),
        (
            "환 영",
            "인도자",
        ),
        (
            "교 회 소 식",
            "인도자",
        ),
        (
            "봉 헌 찬 송",
            page.offering_hymn or "",
        ),
        (
            "봉 헌 기 도",
            _join_services(
                (
                    page.first_service_offering_prayer_display
                    or page.first_service_offering_prayer
                ),
                (
                    page.second_service_offering_prayer_display
                    or page.second_service_offering_prayer
                ),
            ),
        ),
        (
            "성 경 봉 독",
            page.scripture or "",
        ),
        (
            "말 씀 선 포",
            " / ".join(
                value
                for value in (
                    page.sermon_title,
                    page.preacher,
                )
                if value
            ),
        ),
        (
            "결 단 찬 송",
            page.decision_hymn or "",
        ),
        (
            "폐 회 기 도",
            page.closing_prayer or "",
        ),
    )


def build_serving_rows(
    page: BulletinWorshipPage,
) -> tuple[
    tuple[str, str, str, str, str],
    ...,
]:
    return (
        (
            "이번 주 1부",
            page.first_service_prayer or "",
            (
                page.first_service_offering_prayer
                or ""
            ),
            page.this_week_dishwashing or "",
            (
                page.this_week_wednesday_prayer
                or ""
            ),
        ),
        (
            "이번 주 2부",
            page.second_service_prayer or "",
            (
                page.second_service_offering_prayer
                or ""
            ),
            "",
            "",
        ),
        (
            "다음 주 1부",
            page.next_week_first_service_prayer or "",
            (
                page.next_week_first_service_offering_prayer
                or ""
            ),
            page.next_week_dishwashing or "",
            (
                page.next_week_wednesday_prayer
                or ""
            ),
        ),
        (
            "다음 주 2부",
            page.next_week_second_service_prayer or "",
            (
                page.next_week_second_service_offering_prayer
                or ""
            ),
            "",
            "",
        ),
    )


def _draw_section_title(
    canvas: Canvas,
    *,
    text: str,
    x: float,
    y: float,
    width: float,
) -> float:
    canvas.setFont(
        FONT_BOLD,
        12.5,
    )

    canvas.setFillColorRGB(0, 0, 0)
    if text == "오전 예배 순서":
        canvas.drawCentredString(x + width / 2, y, text)
    else:
        canvas.drawString(x, y, f"<{text}>")
    canvas.setFillColorRGB(0, 0, 0)

    canvas.line(
        x,
        y - 2 * mm,
        x + width,
        y - 2 * mm,
    )

    return y - 7 * mm


def draw_worship_page(
    canvas: Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    page: BulletinWorshipPage,
) -> None:
    register_korean_fonts()

    margin = 8 * mm

    left = x + margin
    right = x + width - margin
    content_width = right - left

    cursor = y + height - 14 * mm

    # -------------------------
    # 주일 오전 예배 순서
    # -------------------------

    cursor = _draw_section_title(
        canvas,
        text="오전 예배 순서",
        x=left,
        y=cursor,
        width=content_width,
    )

    if page.leader:
        canvas.setFont(
            FONT_REGULAR,
            9.2,
        )
        canvas.drawRightString(
            right,
            cursor,
            f"인 도 : {page.leader}",
        )
        cursor -= 6 * mm

    label_width = 32 * mm
    row_height = 8.0 * mm

    for label, value in (
        build_worship_order_rows(page)
    ):
        canvas.setFont(
            FONT_BOLD,
            9.2,
        )
        canvas.drawString(
            left,
            cursor,
            label,
        )

        canvas.setFont(
            FONT_REGULAR,
            8.3,
        )

        if value:
            canvas.drawRightString(
                right,
                cursor,
                value,
            )

        canvas.setDash(1.2, 1.2)
        canvas.line(
            left + label_width,
            cursor - 1 * mm,
            right,
            cursor - 1 * mm,
        )

        canvas.setDash()
        cursor -= row_height

    cursor -= 5 * mm

    # -------------------------
    # 예배 / 섬김
    # -------------------------

    cursor = _draw_section_title(
        canvas,
        text="예배 / 섬김",
        x=left,
        y=cursor,
        width=content_width,
    )

    headers = (
        "구분",
        "기도",
        "봉헌기도",
        "설거지",
        "수요기도",
    )

    column_widths = (
        24 * mm,
        20 * mm,
        25 * mm,
        28 * mm,
        25 * mm,
    )

    total_width = sum(column_widths)

    # 위/아래 표의 좌우 끝을 동일하게 맞춘다.
    scale = (
        content_width
        / total_width
    )
    column_widths = tuple(
        value * scale
        for value in column_widths
    )

    table_top = cursor + 3 * mm
    table_x = left
    table_row_height = 6.8 * mm

    rows = build_serving_rows(page)

    all_rows = (
        headers,
        *rows,
    )

    for row_index, row in enumerate(
        all_rows
    ):
        row_top = (
            table_top
            - row_index * table_row_height
        )
        row_bottom = (
            row_top - table_row_height
        )

        column_x = table_x

        for column_index, value in enumerate(
            row
        ):
            column_width = (
                column_widths[
                    column_index
                ]
            )

            canvas.setFillColorRGB(*( (0.82, 0.82, 0.82) if row_index == 0
                                      or column_index == 0 else (1, 1, 1) ))
            canvas.rect(column_x, row_bottom, column_width, table_row_height, fill=1)
            canvas.setFillColorRGB(0, 0, 0)

            canvas.setFont(
                (
                    FONT_BOLD
                    if row_index == 0
                    else FONT_REGULAR
                ),
                7.4,
            )

            canvas.drawCentredString(
                (
                    column_x
                    + column_width / 2
                ),
                row_bottom + 2.2 * mm,
                value,
            )

            column_x += column_width

    cursor = (
        table_top
        - len(all_rows)
        * table_row_height
        - 7 * mm
    )

    canvas.setFont(
        FONT_REGULAR,
        9,
    )

    # Bottom worship information
    # -------------------------

    table_x = left
    table_width = content_width
    table_height = 24 * mm

    # 위쪽 예배/섬김 표의 다음 위치에서 이어서 배치한다.
    table_y = cursor - table_height

    col_width = table_width / 3
    header_height = 8 * mm
    body_height = table_height - header_height
    body_top = table_y + body_height

    headers = (
        ("\uc8fc\uc77c \uc624\uc804", "\uc624\uc804 9:00"),
        ("\uc8fc\uc77c \uc624\ud6c4", "\uc624\ud6c4 1:30"),
        ("\uc218\uc694 \uc608\ubc30", "\uc624\ud6c4 7:30"),
    )

    for index, (title, time_text) in enumerate(headers):
        cell_x = table_x + index * col_width

        canvas.rect(
            cell_x,
            table_y,
            col_width,
            table_height,
        )

        canvas.line(
            cell_x,
            body_top,
            cell_x + col_width,
            body_top,
        )

        canvas.setFont(FONT_BOLD, 8.8)
        canvas.drawCentredString(
            cell_x + col_width / 2,
            body_top + 4.2 * mm,
            title,
        )

        canvas.setFont(FONT_REGULAR, 7.7)
        canvas.drawCentredString(
            cell_x + col_width / 2,
            body_top + 1.4 * mm,
            f"({time_text})",
        )

    # Sunday morning
    canvas.setFont(FONT_BOLD, 9)
    canvas.drawCentredString(
        table_x + col_width / 2,
        body_top - 4.2 * mm,
        "\ud559\uc0dd\ubd80 \uc608\ubc30",
    )

    # Sunday afternoon
    if page.afternoon_service:
        canvas.setFont(FONT_BOLD, 9)
        canvas.drawCentredString(
            table_x + col_width * 1.5,
            body_top - 4.2 * mm,
            page.afternoon_service,
        )

    # Wednesday worship
    wed_x = table_x + col_width * 2
    label_x = wed_x + 4 * mm
    value_x = wed_x + col_width - 4 * mm

    wednesday_rows = (
        ("\ucc2c    \uc591", "\ub2e4   \uac19   \uc774"),
        ("\ub9d0    \uc500", "\uc774\uc740\ucca0 \ubaa9\uc0ac"),
        ("\ud569\uc2ec\uae30\ub3c4", "\ub2e4   \uac19   \uc774"),
    )

    wed_cursor = body_top - 3.5 * mm

    for label, value in wednesday_rows:
        canvas.setFont(FONT_BOLD, 7.7)
        canvas.drawString(
            label_x,
            wed_cursor,
            label,
        )

        canvas.setFont(FONT_REGULAR, 7.7)
        canvas.drawRightString(
            value_x,
            wed_cursor,
            value,
        )

        wed_cursor -= 4.2 * mm
