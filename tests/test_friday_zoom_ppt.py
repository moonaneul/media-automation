from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)
from media_automation.ppt import (
    create_16x9_presentation,
)
from media_automation.ppt.friday_zoom import (
    render_friday_zoom_block,
)


class Topics:
    topics = [
        "첫 번째 기도 제목",
        "두 번째 기도 제목",
    ]


class PersonalPrayer:
    text = None


def test_friday_zoom_prayer_topics_slide():
    prs = create_16x9_presentation()

    block = WorshipBlock(
        kind=BlockKind.PRAYER_TOPICS,
        key="first_prayer",
        value=Topics(),
    )

    render_friday_zoom_block(
        prs,
        block,
    )

    assert len(prs.slides) == 1

    text = "\n".join(
        shape.text
        for shape in prs.slides[0].shapes
        if hasattr(shape, "text")
    )

    assert "첫 번째 기도 제목" in text
    assert "두 번째 기도 제목" in text


def test_friday_zoom_personal_prayer_slide():
    prs = create_16x9_presentation()

    block = WorshipBlock(
        kind=BlockKind.PERSONAL_PRAYER,
        key="personal_prayer",
        value=PersonalPrayer(),
    )

    render_friday_zoom_block(
        prs,
        block,
    )

    assert len(prs.slides) == 1

    text = "\n".join(
        shape.text
        for shape in prs.slides[0].shapes
        if hasattr(shape, "text")
    )

    assert "개인 기도" in text

from media_automation.bible import (
    BiblePassage,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    SermonTitleContent,
)
from media_automation.weekly_data.models import (
    ScriptureField,
    WeeklyStatus,
)


def test_friday_zoom_sermon_title_slide():
    prs = create_16x9_presentation()

    block = WorshipBlock(
        kind=BlockKind.SERMON_TITLE,
        key="sermon_title",
        value=SermonTitleContent(
            title="예시 설교 제목",
            scripture_reference="요 3:16~18",
        ),
    )

    render_friday_zoom_block(
        prs,
        block,
    )

    assert len(prs.slides) == 1

    text = "\n".join(
        shape.text
        for shape in prs.slides[0].shapes
        if hasattr(shape, "text")
    )

    assert "요 3:16~18" in text
    assert "예시 설교 제목" in text


def test_friday_zoom_scripture_can_group_verses():
    prs = create_16x9_presentation()

    provider = InMemoryBibleProvider(
        {
            "요 3:16-18": BiblePassage(
                reference="요 3:16~18",
                verses=(
                    BibleVerse(
                        number=16,
                        text="샘플 본문 16절",
                    ),
                    BibleVerse(
                        number=17,
                        text="샘플 본문 17절",
                    ),
                    BibleVerse(
                        number=18,
                        text="샘플 본문 18절",
                    ),
                ),
            ),
        }
    )

    block = WorshipBlock(
        kind=BlockKind.SCRIPTURE,
        key="scripture",
        value=ScriptureField(
            status=WeeklyStatus.VALUE,
            reference="요 3:16-18",
        ),
    )

    render_friday_zoom_block(
        prs,
        block,
        bible_provider=provider,
    )

    # 짧은 3절도 Zoom에서는
    # 최대 2절씩 표시한다.
    assert len(prs.slides) == 2

    first_slide_text = "\n".join(
        shape.text
        for shape in prs.slides[0].shapes
        if hasattr(shape, "text")
    )

    second_slide_text = "\n".join(
        shape.text
        for shape in prs.slides[1].shapes
        if hasattr(shape, "text")
    )

    assert "16. 샘플 본문 16절" in first_slide_text
    assert "17. 샘플 본문 17절" in first_slide_text
    assert "18. 샘플 본문 18절" not in first_slide_text

    assert "18. 샘플 본문 18절" in second_slide_text