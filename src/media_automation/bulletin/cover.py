from __future__ import annotations

from dataclasses import dataclass

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import (
    UnicodeCIDFont,
)
from reportlab.pdfgen.canvas import Canvas

from media_automation.bulletin.document import (
    BulletinCoverPage,
)


FONT_REGULAR = "HYSMyeongJo-Medium"
FONT_BOLD = "HYSMyeongJo-Medium"


@dataclass(frozen=True, slots=True)
class BulletinCoverStatic:
    church_name: str = (
        "하늘빛기쁨성서침례교회"
    )
    slogan: str = (
        "영혼 구원하여 제자 삼는 교회"
    )
    senior_pastor: str = "\uc774\uc740\ucca0 \ubaa9\uc0ac"
    address: str = (
        "\uc11c\uc6b8\ud2b9\ubcc4\uc2dc \uad6c\ub85c\uad6c \ucc9c\uc655\ub85c 36(\ucc9c\uc655\ub3d9) "
        "\uc13c\ud0c0\ud504\ub77c\uc790 601\ud638"
    )
    phone: str = "02-2611-9191"
    fax: str = "02-2689-9191"
    website: str = "https://hjbbc.or.kr"

    verse_lines: tuple[str, ...] = (
        (
            "그러므로 너희는 가서 모든 민족을 "
            "제자로 삼아 아버지와 아들과 "
            "성령의 이름으로"
        ),
        "침례를 베풀고 (마 28:19)",
    )


def register_korean_fonts() -> None:
    registered = set(
        pdfmetrics.getRegisteredFontNames()
    )

    if FONT_REGULAR not in registered:
        pdfmetrics.registerFont(
            UnicodeCIDFont(
                FONT_REGULAR
            )
        )

    if FONT_BOLD not in registered:
        pdfmetrics.registerFont(
            UnicodeCIDFont(
                FONT_BOLD
            )
        )


def draw_cover_page(
    canvas: Canvas,
    *,
    x: float,
    y: float,
    width: float,
    height: float,
    cover: BulletinCoverPage,
    static: BulletinCoverStatic | None = None,
) -> None:
    register_korean_fonts()

    if static is None:
        static = BulletinCoverStatic()

    margin = 12 * mm
    top = y + height - margin

    # 호수
    if cover.bulletin_number:
        canvas.setFont(
            FONT_REGULAR,
            8.5,
        )
        canvas.drawString(
            x + margin,
            top,
            f"No. {cover.bulletin_number}",
        )

    # 날짜
    canvas.setFont(
        FONT_REGULAR,
        8.5,
    )
    canvas.drawRightString(
        x + width - margin,
        top,
        cover.date_text,
    )

    # 교회명
    canvas.setFont(
        FONT_BOLD,
        18,
    )
    canvas.drawCentredString(
        x + width / 2,
        y + height * 0.66,
        static.church_name,
    )

    # 표어
    canvas.setFont(
        FONT_BOLD,
        14,
    )
    canvas.drawCentredString(
        x + width / 2,
        y + height * 0.54,
        static.slogan,
    )

    # 마 28:19
    canvas.setFont(
        FONT_REGULAR,
        9,
    )

    verse_y = y + height * 0.46

    for index, line in enumerate(
        static.verse_lines
    ):
        canvas.drawCentredString(
            x + width / 2,
            verse_y - index * 5 * mm,
            line,
        )

    # Contact information
    contact_lines = (
        f"\ub2f4\uc784\ubaa9\uc0ac  {static.senior_pastor}",
        static.address,
        f"TEL  {static.phone}    FAX  {static.fax}",
        static.website,
    )

    canvas.setFont(
        FONT_REGULAR,
        7.2,
    )

    contact_y = y + 31 * mm

    for index, line in enumerate(contact_lines):
        canvas.drawCentredString(
            x + width / 2,
            contact_y - index * 4.5 * mm,
            line,
        )
