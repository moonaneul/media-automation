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
    UnsupportedPlanError,
    build_presentation_from_plan,
)
from media_automation.weekly_data.models import (
    PersonField,
    ScriptureField,
)


def test_builder_renders_blank():
    prs = build_presentation_from_plan(
        [
            WorshipBlock(
                kind=BlockKind.BLANK,
                key="blank",
            )
        ]
    )

    assert len(prs.slides) == 1


def test_builder_renders_prayer():
    prs = build_presentation_from_plan(
        [
            WorshipBlock(
                kind=BlockKind.PRAYER,
                key="prayer",
                value=PersonField(
                    status="VALUE",
                    person="홍길동",
                ),
            )
        ]
    )

    assert (
        prs.slides[0]
        .shapes[0]
        .text
        == "기 도 : 홍길동"
    )


def test_builder_renders_sermon_title():
    prs = build_presentation_from_plan(
        [
            WorshipBlock(
                kind=BlockKind.SERMON_TITLE,
                key="sermon_title",
                value=SermonTitleContent(
                    title="외모와 중심",
                    scripture_reference="삼상 16:6-7",
                ),
            )
        ]
    )

    text = prs.slides[0].shapes[0].text

    assert "삼상 16:6-7" in text
    assert "외모와 중심" in text


def test_builder_renders_scripture():
    provider = InMemoryBibleProvider(
        {
            "삼상 16:6-7": BiblePassage(
                reference="삼상 16:6~7",
                verses=(
                    BibleVerse(
                        number=6,
                        text="6절",
                    ),
                    BibleVerse(
                        number=7,
                        text="7절",
                    ),
                ),
            )
        }
    )

    prs = build_presentation_from_plan(
        [
            WorshipBlock(
                kind=BlockKind.SCRIPTURE,
                key="scripture",
                value=ScriptureField(
                    status="VALUE",
                    reference="삼상 16:6-7",
                ),
            )
        ],
        bible_provider=provider,
    )

    assert len(prs.slides) == 2


def test_builder_rejects_song():
    with pytest.raises(
        UnsupportedPlanError
    ):
        build_presentation_from_plan(
            [
                WorshipBlock(
                    kind=BlockKind.SONG,
                    key="song",
                )
            ]
        )


def test_builder_rejects_pre_service():
    with pytest.raises(
        UnsupportedPlanError
    ):
        build_presentation_from_plan(
            [
                WorshipBlock(
                    kind=BlockKind.PRE_SERVICE,
                    key="pre_service",
                )
            ]
        )