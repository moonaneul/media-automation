from reportlab.lib.pagesizes import (
    A4,
    landscape,
)

from media_automation.bulletin.pdf import (
    build_imposition_plan,
    render_bulletin_imposition_preview,
)


def test_bulletin_imposition_order():
    sheets = build_imposition_plan()

    assert len(sheets) == 2

    assert (
        sheets[0].left_page,
        sheets[0].right_page,
    ) == (4, 1)

    assert (
        sheets[1].left_page,
        sheets[1].right_page,
    ) == (2, 3)


def test_render_bulletin_imposition_preview(
    tmp_path,
):
    output = tmp_path / "bulletin.pdf"

    result = (
        render_bulletin_imposition_preview(
            output
        )
    )

    expected_width, expected_height = (
        landscape(A4)
    )

    assert result.path.exists()

    assert result.width == expected_width
    assert result.height == expected_height

    assert result.path.read_bytes().startswith(
        b"%PDF"
    )

    assert len(result.sheets) == 2


def test_render_bulletin_pdf_with_cover(
    tmp_path,
):
    from media_automation.bulletin.document import (
        BulletinCellGroupPage,
        BulletinCoverPage,
        BulletinDocument,
        BulletinNewsPage,
        BulletinWorshipPage,
    )
    from media_automation.bulletin.pdf import (
        render_bulletin_pdf,
    )

    document = BulletinDocument(
        cover=BulletinCoverPage(
            bulletin_number="13-39",
            date_text="2026년 9월 27일",
        ),
        worship=BulletinWorshipPage(
            separate_hymn=None,
            first_service_prayer=None,
            second_service_prayer=None,
            offering_hymn=None,
            first_service_offering_prayer=None,
            second_service_offering_prayer=None,
            scripture=None,
            sermon_title=None,
            decision_hymn=None,
            this_week_dishwashing=None,
            this_week_wednesday_prayer=None,
            next_week_dishwashing=None,
            next_week_wednesday_prayer=None,
            afternoon_service=None,
        ),
        cell_group=BulletinCellGroupPage(
            scripture=None,
            title=None,
            questions=(),
        ),
        news=BulletinNewsPage(
            church_news=(),
            monthly_schedule=(),
        ),
    )

    output = (
        tmp_path
        / "bulletin-cover.pdf"
    )

    result = render_bulletin_pdf(
        document,
        output,
    )

    assert result.path.exists()

    assert result.path.read_bytes().startswith(
        b"%PDF"
    )

    assert (
        result.sheets[0].right_page
        == 1
    )


def test_bulletin_pdf_embeds_korean_font(tmp_path):
    from reportlab.pdfgen.canvas import Canvas
    from media_automation.bulletin.cover import FONT_REGULAR, register_korean_fonts

    register_korean_fonts()
    output = tmp_path / "embedded-korean.pdf"
    canvas = Canvas(str(output))
    canvas.setFont(FONT_REGULAR, 12)
    canvas.drawString(30, 30, "하늘빛기쁨교회 침례")
    canvas.save()
    assert b"/FontFile2" in output.read_bytes()
