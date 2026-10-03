import pytest

from media_automation.bible import (
    BiblePassage,
    BiblePassageNotFoundError,
    BibleVerse,
    InMemoryBibleProvider,
)


def test_in_memory_bible_provider_returns_passage():
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

    provider = InMemoryBibleProvider(
        {
            "삼상 16:6-7": passage,
        }
    )

    assert (
        provider.get_passage(
            "삼상 16:6-7"
        )
        == passage
    )


def test_in_memory_bible_provider_does_not_guess_reference():
    provider = InMemoryBibleProvider(
        {
            "삼상 16:6-7": BiblePassage(
                reference="삼상 16:6~7",
                verses=(),
            ),
        }
    )

    with pytest.raises(
        BiblePassageNotFoundError
    ):
        provider.get_passage(
            "삼상16:6-7"
        )


def test_bible_passage_keeps_verse_order():
    passage = BiblePassage(
        reference="시 24:3~5",
        verses=(
            BibleVerse(
                number=3,
                text="3절",
            ),
            BibleVerse(
                number=4,
                text="4절",
            ),
            BibleVerse(
                number=5,
                text="5절",
            ),
        ),
    )

    assert [
        verse.number
        for verse in passage.verses
    ] == [3, 4, 5]


def test_missing_passage_error_contains_reference():
    provider = InMemoryBibleProvider(
        {}
    )

    with pytest.raises(
        BiblePassageNotFoundError,
        match="시 24:3-5",
    ):
        provider.get_passage(
            "시 24:3-5"
        )