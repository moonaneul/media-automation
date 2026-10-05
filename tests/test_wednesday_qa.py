from media_automation.ppt import (
    WednesdaySlideRange,
    create_4x3_presentation,
    validate_wednesday_structure,
)
from media_automation.ppt.base import (
    add_blank_slide,
)
from media_automation.bible import (
    BiblePassage,
    BibleVerse,
)

def test_wednesday_qa_accepts_valid_structure(
    tmp_path,
):
    output = (
        tmp_path
        / "valid.pptx"
    )

    prs = create_4x3_presentation()

    add_blank_slide(
        prs
    )

    prs.save(
        output
    )

    result = (
        validate_wednesday_structure(
            output,
            slide_ranges={
                (
                    "transition:"
                    "song->prayer"
                ): WednesdaySlideRange(
                    start=1,
                    end=1,
                ),
            },
        )
    )

    assert result.ok
    assert result.issues == ()


def test_wednesday_qa_detects_text_on_transition(
    tmp_path,
):
    output = (
        tmp_path
        / "invalid.pptx"
    )

    prs = create_4x3_presentation()

    slide = add_blank_slide(
        prs
    )

    textbox = slide.shapes.add_textbox(
        0,
        0,
        1000000,
        1000000,
    )

    textbox.text = "있으면 안 되는 글"

    prs.save(
        output
    )

    result = (
        validate_wednesday_structure(
            output,
            slide_ranges={
                (
                    "transition:"
                    "song->prayer"
                ): WednesdaySlideRange(
                    start=1,
                    end=1,
                ),
            },
        )
    )

    assert not result.ok

    assert (
        result.issues[0].code
        == "TRANSITION_NOT_BLANK"
    )


def test_wednesday_qa_detects_baptism_term(
    tmp_path,
):
    output = (
        tmp_path
        / "baptism.pptx"
    )

    prs = create_4x3_presentation()

    slide = add_blank_slide(
        prs
    )

    textbox = slide.shapes.add_textbox(
        0,
        0,
        1000000,
        1000000,
    )

    textbox.text = "세례를 받으니"

    prs.save(
        output
    )

    result = (
        validate_wednesday_structure(
            output,
            slide_ranges={},
        )
    )

    assert not result.ok

    assert any(
        issue.code
        == "BAPTISM_TERM_NOT_CONVERTED"
        for issue in result.issues
    )
def test_wednesday_qa_detects_scripture_slide_count_mismatch(
    tmp_path,
):
    output = tmp_path / "scripture-count.pptx"

    prs = create_4x3_presentation()
    add_blank_slide(prs)
    prs.save(output)

    passage = BiblePassage(
        reference="삼상 16:6~7",
        verses=(
            BibleVerse(
                number=6,
                text="6절 본문",
            ),
            BibleVerse(
                number=7,
                text="7절 본문",
            ),
        ),
    )

    result = validate_wednesday_structure(
        output,
        slide_ranges={
            "scripture": WednesdaySlideRange(
                start=1,
                end=1,
            ),
        },
        scripture_passages={
            "scripture": passage,
        },
    )

    assert not result.ok
    assert any(
        issue.code
        == "SCRIPTURE_SLIDE_COUNT_MISMATCH"
        for issue in result.issues
    )


def test_wednesday_qa_detects_scripture_reference_mismatch(
    tmp_path,
):
    output = tmp_path / "scripture-reference.pptx"

    prs = create_4x3_presentation()
    slide = add_blank_slide(prs)

    textbox = slide.shapes.add_textbox(
        0,
        0,
        4000000,
        2000000,
    )
    textbox.text = (
        "삼상 16:8~8\n"
        "6.\n"
        "6절 본문"
    )

    prs.save(output)

    passage = BiblePassage(
        reference="삼상 16:6~6",
        verses=(
            BibleVerse(
                number=6,
                text="6절 본문",
            ),
        ),
    )

    result = validate_wednesday_structure(
        output,
        slide_ranges={
            "scripture": WednesdaySlideRange(
                start=1,
                end=1,
            ),
        },
        scripture_passages={
            "scripture": passage,
        },
    )

    assert not result.ok
    assert any(
        issue.code
        == "SCRIPTURE_REFERENCE_MISMATCH"
        for issue in result.issues
    )


def test_wednesday_qa_detects_scripture_verse_number_mismatch(
    tmp_path,
):
    output = tmp_path / "scripture-verse-number.pptx"

    prs = create_4x3_presentation()
    slide = add_blank_slide(prs)

    textbox = slide.shapes.add_textbox(
        0,
        0,
        4000000,
        2000000,
    )
    textbox.text = (
        "삼상 16:6~6\n"
        "7.\n"
        "6절 본문"
    )

    prs.save(output)

    passage = BiblePassage(
        reference="삼상 16:6~6",
        verses=(
            BibleVerse(
                number=6,
                text="6절 본문",
            ),
        ),
    )

    result = validate_wednesday_structure(
        output,
        slide_ranges={
            "scripture": WednesdaySlideRange(
                start=1,
                end=1,
            ),
        },
        scripture_passages={
            "scripture": passage,
        },
    )

    assert not result.ok
    assert any(
        issue.code
        == "SCRIPTURE_VERSE_NUMBER_MISMATCH"
        for issue in result.issues
    )


def test_wednesday_qa_detects_standalone_alignment_error(
    tmp_path,
):
    output = tmp_path / "alignment.pptx"

    prs = create_4x3_presentation()
    slide = add_blank_slide(prs)

    textbox = slide.shapes.add_textbox(
        0,
        0,
        4000000,
        2000000,
    )
    textbox.text = "기 도 : 홍길동"

    prs.save(output)

    result = validate_wednesday_structure(
        output,
        slide_ranges={
            "prayer": WednesdaySlideRange(
                start=1,
                end=1,
            ),
        },
    )

    assert not result.ok

    codes = {
        issue.code
        for issue in result.issues
    }

    assert (
        "STANDALONE_NOT_VERTICALLY_CENTERED"
        in codes
    )
    assert (
        "STANDALONE_NOT_HORIZONTALLY_CENTERED"
        in codes
    )

def test_wednesday_qa_detects_visible_url(
    tmp_path,
):
    output = tmp_path / "visible-url.pptx"

    prs = create_4x3_presentation()
    slide = add_blank_slide(prs)

    textbox = slide.shapes.add_textbox(
        0,
        0,
        4000000,
        1000000,
    )
    textbox.text = (
        "https://example.com/shop"
    )

    prs.save(output)

    result = validate_wednesday_structure(
        output,
        slide_ranges={},
    )

    assert not result.ok

    assert any(
        issue.code
        == "VISIBLE_URL_FOUND"
        for issue in result.issues
    )


def test_wednesday_qa_detects_hyperlink(
    tmp_path,
):
    output = tmp_path / "hyperlink.pptx"

    prs = create_4x3_presentation()
    slide = add_blank_slide(prs)

    textbox = slide.shapes.add_textbox(
        0,
        0,
        4000000,
        1000000,
    )
    textbox.text = "클릭"

    textbox.click_action.hyperlink.address = (
        "https://example.com"
    )

    prs.save(output)

    result = validate_wednesday_structure(
        output,
        slide_ranges={},
    )

    assert not result.ok

    assert any(
        issue.code
        == "HYPERLINK_FOUND"
        for issue in result.issues
    )