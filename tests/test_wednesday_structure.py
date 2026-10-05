from pathlib import Path

from pptx import Presentation

from media_automation.bible import (
    BiblePassage,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)
from media_automation.ppt import (
    FilePreServiceSlideProvider,
    FileSongAssetProvider,
    build_wednesday_structure,
)
from media_automation.ppt.base import (
    add_blank_slide,
    create_4x3_presentation,
)
from media_automation.weekly_data.models import (
    ScriptureField,
    Song,
    WeeklyStatus,
)


def make_ppt(
    path: Path,
    slide_count: int,
) -> None:
    prs = create_4x3_presentation()

    for _ in range(
        slide_count
    ):
        add_blank_slide(
            prs
        )

    prs.save(
        path
    )


def test_wednesday_structure_uses_real_song_slide_count(
    tmp_path,
):
    pre_service = (
        tmp_path
        / "pre_service.pptx"
    )

    song_path = (
        tmp_path
        / "song.pptx"
    )

    output = (
        tmp_path
        / "wednesday.pptx"
    )

    # 예배 전 안내 4장
    make_ppt(
        pre_service,
        4,
    )

    # 악보 PPT 3장
    make_ppt(
        song_path,
        3,
    )

    plan = [
        WorshipBlock(
            kind=BlockKind.PRE_SERVICE,
            key="pre_service",
        ),
        WorshipBlock(
            kind=BlockKind.SONG,
            key="opening_songs[0]",
            value=Song(
                status=WeeklyStatus.VALUE,
                title="테스트 찬양",
            ),
        ),
        WorshipBlock(
            kind=BlockKind.BLANK,
            key=(
                "transition:"
                "opening_songs[0]"
                "->scripture"
            ),
        ),
        WorshipBlock(
            kind=BlockKind.SCRIPTURE,
            key="scripture",
            value=ScriptureField(
                status=WeeklyStatus.VALUE,
                reference="요 3:16-17",
            ),
        ),
    ]

    bible = InMemoryBibleProvider(
        {
            "요 3:16-17": BiblePassage(
                reference="요 3:16~17",
                verses=(
                    BibleVerse(
                        number=16,
                        text="샘플 16절",
                    ),
                    BibleVerse(
                        number=17,
                        text="샘플 17절",
                    ),
                ),
            ),
        }
    )

    pre_service_provider = (
        FilePreServiceSlideProvider(
            {
                "pre_service": (
                    pre_service
                ),
            },
            slide_counts={
                "pre_service": 4,
            },
        )
    )

    song_provider = (
        FileSongAssetProvider(
            {
                "테스트 찬양": (
                    song_path
                ),
            }
        )
    )

    result = (
        build_wednesday_structure(
            plan,
            output,
            bible_provider=bible,
            pre_service_provider=(
                pre_service_provider
            ),
            song_asset_provider=(
                song_provider
            ),
        )
    )

    prs = Presentation(
        output
    )

    # 4장 안내
    # + 3장 악보 placeholder
    # + 1장 빈 화면
    # + 성경 2절
    assert len(prs.slides) == 10

    ranges = result.slide_ranges

    assert (
        ranges["pre_service"].start
        == 1
    )
    assert (
        ranges["pre_service"].end
        == 4
    )

    assert (
        ranges[
            "opening_songs[0]"
        ].start
        == 5
    )
    assert (
        ranges[
            "opening_songs[0]"
        ].end
        == 7
    )

    assert (
        ranges[
            "transition:"
            "opening_songs[0]"
            "->scripture"
        ].start
        == 8
    )

    assert (
        ranges["scripture"].start
        == 9
    )
    assert (
        ranges["scripture"].end
        == 10
    )