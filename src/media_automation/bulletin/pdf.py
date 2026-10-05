from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen.canvas import Canvas

from media_automation.bulletin.cover import (
    draw_cover_page,
)
from media_automation.bulletin.document import (
    BulletinDocument,
)
from media_automation.bulletin.worship_page import (
    draw_worship_page,
)
from media_automation.bulletin.cell_group_page import (
    draw_cell_group_page,
)
from media_automation.bulletin.news_page import (
    draw_news_page,
)


@dataclass(frozen=True, slots=True)
class BulletinSheet:
    sheet_number: int
    left_page: int
    right_page: int


@dataclass(frozen=True, slots=True)
class BulletinPdfResult:
    path: Path
    sheets: tuple[BulletinSheet, ...]
    width: float
    height: float


def build_imposition_plan() -> tuple[
    BulletinSheet,
    ...,
]:
    return (
        BulletinSheet(
            sheet_number=1,
            left_page=4,
            right_page=1,
        ),
        BulletinSheet(
            sheet_number=2,
            left_page=2,
            right_page=3,
        ),
    )


def _draw_logical_page_placeholder(
    canvas: Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    logical_page: int,
) -> None:
    canvas.setFont(
        "Helvetica-Bold",
        20,
    )

    canvas.drawCentredString(
        x + width / 2,
        y + height / 2,
        f"PAGE {logical_page}",
    )


def _draw_logical_page(
    canvas: Canvas,
    *,
    document: BulletinDocument,
    logical_page: int,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    if logical_page == 1:
        draw_cover_page(
            canvas,
            x=x,
            y=y,
            width=width,
            height=height,
            cover=document.cover,
        )
        return

    if logical_page == 2:
        draw_worship_page(
            canvas,
            x=x,
            y=y,
            width=width,
            height=height,
            page=document.worship,
        )
        return

    if logical_page == 3:
        draw_cell_group_page(
            canvas,
            x=x,
            y=y,
            width=width,
            height=height,
            page=document.cell_group,
        )
        return

    if logical_page == 4:
        draw_news_page(
            canvas,
            x=x,
            y=y,
            width=width,
            height=height,
            page=document.news,
        )
        return

    _draw_logical_page_placeholder(
        canvas,
        x=x,
        y=y,
        width=width,
        height=height,
        logical_page=logical_page,
    )


def render_bulletin_pdf(
    document: BulletinDocument,
    output_path: str | Path,
) -> BulletinPdfResult:
    output = Path(output_path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    width, height = landscape(A4)
    half_width = width / 2

    sheets = build_imposition_plan()

    canvas = Canvas(
        str(output),
        pagesize=(width, height),
    )

    for sheet in sheets:
        _draw_logical_page(
            canvas,
            document=document,
            logical_page=sheet.left_page,
            x=0,
            y=0,
            width=half_width,
            height=height,
        )

        _draw_logical_page(
            canvas,
            document=document,
            logical_page=sheet.right_page,
            x=half_width,
            y=0,
            width=half_width,
            height=height,
        )

        canvas.showPage()

    canvas.save()

    return BulletinPdfResult(
        path=output,
        sheets=sheets,
        width=width,
        height=height,
    )


def render_bulletin_imposition_preview(
    output_path: str | Path,
) -> BulletinPdfResult:
    """
    접지 순서만 검사할 때 쓰는 단순 preview.
    """
    width, height = landscape(A4)
    half_width = width / 2
    output = Path(output_path)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    sheets = build_imposition_plan()

    canvas = Canvas(
        str(output),
        pagesize=(width, height),
    )

    for sheet in sheets:
        for logical_page, x in (
            (
                sheet.left_page,
                0,
            ),
            (
                sheet.right_page,
                half_width,
            ),
        ):
            _draw_logical_page_placeholder(
                canvas,
                x=x,
                y=0,
                width=half_width,
                height=height,
                logical_page=logical_page,
            )

        canvas.showPage()

    canvas.save()

    return BulletinPdfResult(
        path=output,
        sheets=sheets,
        width=width,
        height=height,
    )
