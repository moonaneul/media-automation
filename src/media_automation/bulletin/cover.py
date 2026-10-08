from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

from media_automation.bulletin.document import (
    BulletinCoverPage,
)


FONT_REGULAR = "BulletinKorean"
FONT_BOLD = "BulletinKorean"


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
    if FONT_REGULAR in pdfmetrics.getRegisteredFontNames():
        return

    configured = os.environ.get("MEDIA_BULLETIN_FONT")
    if configured:
        candidates = [Path(configured).expanduser()]
    else:
        candidates = [
            Path("/System/Library/Fonts/Supplemental/AppleGothic.ttf"),
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/malgun.ttf",
            Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        ]
    for candidate in candidates:
        if candidate.is_file():
            # Embed the font so PDF viewers do not require Adobe Korea maps
            # or locally installed substitute fonts.
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(candidate)))
            return
    raise RuntimeError(
        "주보 PDF에 포함할 한글 TTF 글꼴이 없습니다. "
        "MEDIA_BULLETIN_FONT에 사용할 한글 글꼴 파일 경로를 지정해주세요."
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
        background = Path(__file__).resolve().parents[3] / "assets/bulletin/cover_autumn.jpg"
        if background.is_file():
            canvas.saveState()
            canvas.drawImage(str(background), x, y, width=width, height=height,
                             preserveAspectRatio=True, anchor="c")
            canvas.setFillColorRGB(0, 0, 0)
            canvas.setFont(FONT_REGULAR, 9.5)
            if cover.bulletin_number:
                canvas.drawString(x + 10 * mm, y + height - 11 * mm,
                                  f"No. {cover.bulletin_number}")
            canvas.drawRightString(x + width - 10 * mm, y + height - 11 * mm,
                                  cover.date_text)
            canvas.setFont(FONT_BOLD, 20)
            canvas.drawCentredString(x + width / 2, y + height * 0.805, static.slogan)
            canvas.setFont(FONT_REGULAR, 9)
            for index, line in enumerate(static.verse_lines):
                canvas.drawCentredString(x + width / 2,
                                        y + height * 0.745 - index * 4.5 * mm, line)
            canvas.restoreState()
            return
        raise FileNotFoundError(f"주보 표지 원본 이미지가 없습니다: {background}")

    margin = 10 * mm
    top = y + height - margin

    # 호수
    if cover.bulletin_number:
        canvas.setFont(
            FONT_REGULAR,
            9.5,
        )
        canvas.drawString(
            x + margin,
            top,
            f"No. {cover.bulletin_number}",
        )

    # 날짜
    canvas.setFont(
        FONT_REGULAR,
        9.5,
    )
    canvas.drawRightString(
        x + width - margin,
        top,
        cover.date_text,
    )

    # 교회명
    canvas.setFont(
        FONT_BOLD,
        26,
    )
    canvas.drawCentredString(
        x + width / 2,
        y + height * 0.70,
        static.church_name,
    )

    # 표어
    canvas.setFont(
        FONT_BOLD,
        17,
    )
    canvas.drawCentredString(
        x + width / 2,
        y + height * 0.57,
        static.slogan,
    )

    # 마 28:19
    canvas.setFont(
        FONT_REGULAR,
        10.5,
    )

    verse_y = y + height * 0.48

    for index, line in enumerate(
        static.verse_lines
    ):
        canvas.drawCentredString(
            x + width / 2,
            verse_y - index * 6 * mm,
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
        8.4,
    )

    contact_y = y + 35 * mm

    for index, line in enumerate(contact_lines):
        canvas.drawCentredString(
            x + width / 2,
            contact_y - index * 5 * mm,
            line,
        )
