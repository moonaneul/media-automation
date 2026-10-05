from __future__ import annotations

from functools import lru_cache
from io import BytesIO

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import (
    MSO_ANCHOR,
    PP_ALIGN,
)
from pptx.util import Inches, Pt

from media_automation.bible import (
    BiblePassage,
    BibleProvider,
)
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)

from .base import add_blank_slide
from .renderer import (
    MissingRenderDependencyError,
)
from .scripture import (
    _display_bible_text,
    _validate_passage,
)

@lru_cache(maxsize=1)
def _zoom_background_image() -> bytes:
    """
    기존 금요 Zoom 자료의
    청록 → 적갈색 → 금색 계열 배경을
    간단한 4-corner gradient로 재현한다.
    """

    width = 640
    height = 360

    image = Image.new(
        "RGB",
        (width, height),
    )

    pixels = image.load()

    top_left = (119, 78, 83)
    top_right = (190, 151, 78)
    bottom_left = (48, 91, 94)
    bottom_right = (164, 103, 82)

    for y in range(height):
        ty = y / (height - 1)

        for x in range(width):
            tx = x / (width - 1)

            color = []

            for index in range(3):
                top = (
                    top_left[index]
                    * (1 - tx)
                    + top_right[index]
                    * tx
                )

                bottom = (
                    bottom_left[index]
                    * (1 - tx)
                    + bottom_right[index]
                    * tx
                )

                value = (
                    top * (1 - ty)
                    + bottom * ty
                )

                color.append(int(value))

            pixels[x, y] = tuple(color)

    buffer = BytesIO()

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def add_zoom_background(
    prs: Presentation,
    slide,
):
    slide.shapes.add_picture(
        BytesIO(
            _zoom_background_image()
        ),
        0,
        0,
        width=prs.slide_width,
        height=prs.slide_height,
    )


def add_zoom_rule(
    slide,
    *,
    left: float,
    top: float,
    width: float,
):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left),
        Inches(top),
        Inches(width),
        Inches(0.025),
    )

    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(
        235,
        235,
        235,
    )

    shape.line.fill.background()

    return shape

def add_zoom_centered_text_slide(
    prs: Presentation,
    text: str,
    *,
    font_size: int = 36,
):
    slide = add_blank_slide(prs)
    add_zoom_background(
        prs,
        slide,
    )
    textbox = slide.shapes.add_textbox(
        Inches(1.2),
        Inches(0.8),
        Inches(10.93),
        Inches(5.9),
    )

    frame = textbox.text_frame
    frame.clear()
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.word_wrap = True

    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.alignment = PP_ALIGN.CENTER

    for run in paragraph.runs:
        run.font.size = Pt(font_size)
        run.font.color.rgb = RGBColor(
            255,
            255,
            255,
        )

    return slide


def add_prayer_topics_slide(
    prs: Presentation,
    topics: list[str],
):
    slide = add_blank_slide(prs)

    add_zoom_background(
        prs,
        slide,
    )
    textbox = slide.shapes.add_textbox(
        Inches(1.4),
        Inches(0.9),
        Inches(10.53),
        Inches(5.7),
    )

    frame = textbox.text_frame
    frame.clear()
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.word_wrap = True

    for index, topic in enumerate(
        topics,
        start=1,
    ):
        paragraph = (
            frame.paragraphs[0]
            if index == 1
            else frame.add_paragraph()
        )

        paragraph.text = (
            f"{index}. {topic}"
        )
        paragraph.alignment = PP_ALIGN.LEFT
        paragraph.space_after = Pt(18)
        paragraph.line_spacing = 1.35

        for run in paragraph.runs:
            run.font.size = Pt(30)
            run.font.color.rgb = RGBColor(
                255,
                255,
                255,
            )

    return slide


def add_zoom_sermon_title_slide(
    prs: Presentation,
    title: str,
    scripture_reference: str,
):
    slide = add_blank_slide(prs)
    add_zoom_background(
        prs,
        slide,
    )

    textbox = slide.shapes.add_textbox(
        Inches(1.2),
        Inches(0.8),
        Inches(10.93),
        Inches(5.9),
    )

    frame = textbox.text_frame
    frame.clear()
    frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    frame.word_wrap = True

    reference = frame.paragraphs[0]
    reference.text = scripture_reference
    reference.alignment = PP_ALIGN.CENTER

    for run in reference.runs:
        run.font.size = Pt(30)
        run.font.color.rgb = RGBColor(
            255,
            255,
            255,
        )

    title_paragraph = frame.add_paragraph()
    title_paragraph.text = title
    title_paragraph.alignment = PP_ALIGN.CENTER
    title_paragraph.space_before = Pt(20)

    for run in title_paragraph.runs:
        run.font.size = Pt(40)
        run.font.color.rgb = RGBColor(
            255,
            255,
            255,
        )

    return slide


def _group_zoom_verses(
    passage: BiblePassage,
    *,
    max_verses: int = 3,
    max_lines: int = 7,
    characters_per_line: int = 30,
):
    """
    금요 Zoom 본문을 실제 화면 분량에 맞춰 묶는다.

    2026-09-04 / 09-11 / 09-18 실제 PPT를 기준으로
    한 화면에 최대 3절까지 허용하되,
    예상 줄 수가 너무 많으면 먼저 분리한다.

    실제 렌더링 QA는 별도 수행한다.
    """

    groups = []
    current = []
    current_lines = 0

    for verse in passage.verses:
        display_text = _display_bible_text(
            verse.text
        )

        estimated_lines = max(
            1,
            (
                len(display_text)
                + characters_per_line
                - 1
            )
            // characters_per_line,
        )

        too_many_verses = (
            current
            and len(current) >= max_verses
        )

        too_many_lines = (
            current
            and (
                current_lines
                + estimated_lines
                > max_lines
            )
        )

        if (
            too_many_verses
            or too_many_lines
        ):
            groups.append(current)
            current = []
            current_lines = 0

        current.append(verse)
        current_lines += estimated_lines

    if current:
        groups.append(current)

    return groups

def add_zoom_scripture_reference_slide(
    prs: Presentation,
    reference: str,
):
    """
    기존 금요 Zoom PPT의 본문 안내 화면.

    실제 자료처럼 본문 범위만
    한 화면에 크게 표시한다.
    """

    return add_zoom_centered_text_slide(
        prs,
        reference,
        font_size=54,
    )

def add_zoom_scripture_passage_slides(
    prs: Presentation,
    passage: BiblePassage,
):
    _validate_passage(passage)

    groups = _group_zoom_verses(
        passage
    )

    slides = []

    for group in groups:
        slide = add_blank_slide(prs)
        add_zoom_background(
            prs,
            slide,
        )

        # 본문 범위
        reference_box = (
            slide.shapes.add_textbox(
                Inches(4.2),
                Inches(0.45),
                Inches(4.9),
                Inches(0.55),
            )
        )

        reference_frame = (
            reference_box.text_frame
        )

        reference_frame.clear()
        reference_frame.word_wrap = True

        reference_paragraph = (
            reference_frame.paragraphs[0]
        )

        reference_paragraph.text = (
            passage.reference
        )

        reference_paragraph.alignment = (
            PP_ALIGN.CENTER
        )

        for run in reference_paragraph.runs:
            run.font.size = Pt(24)
            run.font.color.rgb = RGBColor(
                255,
                255,
                255,
            )

        add_zoom_rule(
            slide,
            left=4.2,
            top=1.02,
            width=4.9,
        )
        # 본문
        body_box = slide.shapes.add_textbox(
            Inches(1.25),
            Inches(1.45),
            Inches(10.8),
            Inches(5.25),
        )

        body_frame = body_box.text_frame
        body_frame.clear()
        body_frame.word_wrap = True

        total_length = sum(
            len(
                _display_bible_text(
                    verse.text
                )
            )
            for verse in group
        )

        font_size = (
            26
            if total_length >= 230
            else 28
        )

        for index, verse in enumerate(
            group
        ):
            paragraph = (
                body_frame.paragraphs[0]
                if index == 0
                else body_frame.add_paragraph()
            )

            paragraph.text = (
                f"{verse.number}. "
                f"{_display_bible_text(verse.text)}"
            )

            paragraph.alignment = (
                PP_ALIGN.LEFT
            )

            paragraph.line_spacing = 1.4
            paragraph.space_after = Pt(12)

            for run in paragraph.runs:
                run.font.size = Pt(
                    font_size
                )
                run.font.color.rgb = RGBColor(
                    255,
                    255,
                    255,
                )

        slides.append(slide)

    return slides

def add_personal_prayer_slide(
    prs: Presentation,
):
    slide = add_blank_slide(prs)

    add_zoom_background(
        prs,
        slide,
    )

    add_zoom_rule(
        slide,
        left=4.4,
        top=2.65,
        width=4.55,
    )

    textbox = slide.shapes.add_textbox(
        Inches(4.0),
        Inches(2.9),
        Inches(5.35),
        Inches(1.0),
    )

    frame = textbox.text_frame
    frame.clear()
    frame.vertical_anchor = (
        MSO_ANCHOR.MIDDLE
    )

    paragraph = frame.paragraphs[0]

    paragraph.text = "개인 기도 시간"

    paragraph.alignment = (
        PP_ALIGN.CENTER
    )

    for run in paragraph.runs:
        run.font.size = Pt(30)
        run.font.color.rgb = RGBColor(
            255,
            255,
            255,
        )

    add_zoom_rule(
        slide,
        left=4.4,
        top=3.95,
        width=4.55,
    )

    return slide

def render_friday_zoom_block(
    prs: Presentation,
    block: WorshipBlock,
    *,
    bible_provider: BibleProvider | None = None,
    include_scripture_reference_slide: bool = False,
):
    if block.kind == BlockKind.BLANK:
        return add_blank_slide(prs)

    if block.kind == BlockKind.PRAYER_TOPICS:
        return add_prayer_topics_slide(
            prs,
            block.value.topics,
        )

    if block.kind == BlockKind.PERSONAL_PRAYER:
        return add_personal_prayer_slide(
            prs
        )

    if block.kind == BlockKind.SERMON_TITLE:
        return add_zoom_sermon_title_slide(
            prs,
            block.value.title,
            block.value.scripture_reference,
        )

    if block.kind == BlockKind.SCRIPTURE:
        if bible_provider is None:
            raise MissingRenderDependencyError(
                "금요 Zoom SCRIPTURE 블록을 "
                "렌더링하려면 BibleProvider가 "
                "필요합니다."
            )

        passage = (
            bible_provider.get_passage(
                block.value.reference
            )
        )

        slides = []

        if include_scripture_reference_slide:
            slides.append(
                add_zoom_scripture_reference_slide(
                    prs,
                    passage.reference,
                )
            )

        slides.extend(
            add_zoom_scripture_passage_slides(
                prs,
                passage,
            )
        )

        return slides

    raise ValueError(
        "금요 Zoom renderer가 "
        f"아직 지원하지 않는 블록입니다: "
        f"{block.kind}"
    )