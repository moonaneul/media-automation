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
        11,
    )

    canvas.drawString(
        x,
        y,
        text,
    )

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

    margin = 10 * mm

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
            8.3,
        )
        canvas.drawRightString(
            right,
            cursor,
            f"인 도 : {page.leader}",
        )
        cursor -= 6 * mm

    label_width = 32 * mm
    row_height = 7 * mm

    for label, value in (
        build_worship_order_rows(page)
    ):
        canvas.setFont(
            FONT_BOLD,
            8.3,
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

        canvas.line(
            left + label_width,
            cursor - 1 * mm,
            right,
            cursor - 1 * mm,
        )

        cursor -= row_height

    cursor -= 3 * mm

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

    if total_width > content_width:
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
    table_row_height = 8 * mm

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

            canvas.rect(
                column_x,
                row_bottom,
                column_width,
                table_row_height,
            )

            canvas.setFont(
                (
                    FONT_BOLD
                    if row_index == 0
                    else FONT_REGULAR
                ),
                6.8,
            )

            canvas.drawCentredString(
                (
                    column_x
                    + column_width / 2
                ),
                row_bottom + 2.7 * mm,
                value,
            )

            column_x += column_width

    cursor = (
        table_top
        - len(all_rows)
        * table_row_height
        - 7 * mm
    )

    # -------------------------
    # 주일 오후
    # -------------------------

    cursor = _draw_section_title(
        canvas,
        text="주일 오후",
        x=left,
        y=cursor,
        width=content_width,
    )

    canvas.setFont(
        FONT_REGULAR,
        9,
    )

    if page.afternoon_service:
        canvas.drawString(
            left,
            cursor,
            page.afternoon_service,
        )
