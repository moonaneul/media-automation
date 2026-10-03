import pytest

from media_automation.bible import (
    BiblePassage,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    BlockKind,
    SermonTitleContent,
    WorshipBlock,
)
from media_automation.ppt import (
    MissingRenderDependencyError,
    create_4x3_presentation,
    render_block,
)
from media_automation.weekly_data.models import (
    PersonField,
    ScriptureField,
)


def test_render_blank():
    prs = create_4x3_presentation()

    render_block(
        prs,
        WorshipBlock(
            kind=BlockKind.BLANK,
            key="blank",
        ),
    )

    assert len(prs.slides) == 1


def test_render_prayer():
    prs = create_4x3_presentation()

    block = WorshipBlock(
        kind=BlockKind.PRAYER,
        key="prayer",
        value=PersonField(
            status="VALUE",
            person="홍길동",
        ),
    )

    render_block(
        prs,
        block,
    )

    assert (
        prs.slides[0]
        .shapes[0]
        .text
        == "기 도 : 홍길동"
    )


def test_render_sermon_title():
    prs = create_4x3_presentation()

    block = WorshipBlock(
        kind=BlockKind.SERMON_TITLE,
        key="sermon_title",
        value=SermonTitleContent(
            title="외모와 중심",
            scripture_reference="삼상 16:6-7",
        ),
    )

    render_block(
        prs,
        block,
    )

    text = (
        prs.slides[0]
        .shapes[0]
        .text
    )

    assert "삼상 16:6-7" in text
    assert "외모와 중심" in text


def test_scripture_requires_bible_provider():
    prs = create_4x3_presentation()

    block = WorshipBlock(
        kind=BlockKind.SCRIPTURE,
        key="scripture",
        value=ScriptureField(
            status="VALUE",
            reference="삼상 16:6-7",
        ),
    )

    with pytest.raises(
        MissingRenderDependencyError
    ):
        render_block(
            prs,
            block,
        )


def test_render_scripture():
    prs = create_4x3_presentation()

    provider = InMemoryBibleProvider(
        {
            "삼상 16:6-7": BiblePassage(
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
        }
    )

    block = WorshipBlock(
        kind=BlockKind.SCRIPTURE,
        key="scripture",
        value=ScriptureField(
            status="VALUE",
            reference="삼상 16:6-7",
        ),
    )

    render_block(
        prs,
        block,
        bible_provider=provider,
    )

    assert len(prs.slides) == 2


def test_render_church_news():
    prs = create_4x3_presentation()

    block = WorshipBlock(
        kind=BlockKind.CHURCH_NEWS,
        key="church_news",
    )

    render_block(
        prs,
        block,
    )

    assert (
        prs.slides[0]
        .shapes[0]
        .text
        == "교회 소식"
    )


def test_renderer_rejects_song_block():
    prs = create_4x3_presentation()

    with pytest.raises(
        ValueError,
        match="지원하지 않는",
    ):
        render_block(
            prs,
            WorshipBlock(
                kind=BlockKind.SONG,
                key="song",
            ),
        )