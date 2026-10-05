import pytest

from reportlab.lib.units import mm

from media_automation.bulletin.cell_group_page import (
    draw_cell_group_page,
    wrap_text,
)
from media_automation.bulletin.cover import (
    FONT_REGULAR,
    register_korean_fonts,
)
from media_automation.bulletin.document import (
    BulletinCellGroupPage,
)


def test_wrap_long_korean_text():
    register_korean_fonts()

    lines = wrap_text(
        (
            "여러분은 보이지 않는 것을 "
            "보는 것처럼 행동하는 믿음을 "
            "실제 삶에서 경험한 적이 있나요?"
        ),
        font_name=FONT_REGULAR,
        font_size=9,
        max_width=55 * mm,
    )

    assert len(lines) >= 2

    assert "".join(
        line.replace(" ", "")
        for line in lines
    ) == (
        "여러분은보이지않는것을"
        "보는것처럼행동하는믿음을"
        "실제삶에서경험한적이있나요?"
    )


def test_cell_group_requires_four_questions(
    tmp_path,
):
    from reportlab.pdfgen.canvas import Canvas

    output = tmp_path / "test.pdf"

    canvas = Canvas(
        str(output)
    )

    page = BulletinCellGroupPage(
        scripture="히 11:1~3",
        title="살아 있는 믿음",
        questions=(
            "질문 1",
            "질문 2",
            "질문 3",
        ),
    )

    with pytest.raises(
        ValueError,
        match="4개",
    ):
        draw_cell_group_page(
            canvas,
            x=0,
            y=0,
            width=148.5 * mm,
            height=210 * mm,
            page=page,
        )
