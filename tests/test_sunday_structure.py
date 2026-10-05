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
    build_in_person_structure,
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

    for _ in range(slide_count):
        add_blank_slide(prs)

    prs.save(path)


def test_sunday_structure_keeps_leading_and_trailing_blanks(
    tmp_path,
):
    pre_service = tmp_path / "pre_service.pptx"
    song_path = tmp_path / "song.pptx"
    output = tmp_path / "sunday.pptx"

    # 예배 전 안내 4장
    make_ppt(
        pre_service,
        4,
    )

    # 악보 3장
    make_ppt(
        song_path,
        3,
    )

    plan = [
        WorshipBlock(
            kind=BlockKind.PRE_SERVICE,
            key="pre_service",
        ),

        # 주일은 예배 전 안내 뒤 빈 화면 유지
        WorshipBlock(
            kind=BlockKind.BLANK,
            key=(
                "transition:"
                "pre_service"
                "->worship.opening_songs[0]"
            ),
        ),

        WorshipBlock(
            kind=BlockKind.SONG,
            key="worship.opening_songs[0]",
            value=Song(
                status=WeeklyStatus.VALUE,
                title="테스트 찬양",
            ),
        ),

        WorshipBlock(
            kind=BlockKind.BLANK,
            key=(
                "transition:"
                "worship.opening_songs[0]"
                "->worship.scripture"
            ),
        ),

        WorshipBlock(
            kind=BlockKind.SCRIPTURE,
            key="worship.scripture",
            value=ScriptureField(
                status=WeeklyStatus.VALUE,
                reference="요 3:16-17",
            ),
        ),

        # 주일은 마지막에도 빈 화면 유지
        WorshipBlock(
            kind=BlockKind.BLANK,
            key=(
                "transition:"
                "worship.scripture"
                "->end"
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
                "pre_service": pre_service,
            },
            slide_counts={
                "pre_service": 4,
            },
        )
    )

    song_provider = (
        FileSongAssetProvider(
            {
                "테스트 찬양": song_path,
            }
        )
    )

    result = build_in_person_structure(
        plan,
        output,
        bible_provider=bible,
        pre_service_provider=(
            pre_service_provider
        ),
        song_asset_provider=(
            song_provider
        ),
        preserve_blank_after_pre_service=True,
        preserve_trailing_blank=True,
    )

    prs = Presentation(output)

    # 4 안내
    # + 1 시작 빈 화면
    # + 3 악보
    # + 1 전환 빈 화면
    # + 2 성경
    # + 1 마지막 빈 화면
    assert len(prs.slides) == 12

    ranges = result.slide_ranges

    assert (
        ranges[
            "transition:"
            "pre_service"
            "->worship.opening_songs[0]"
        ].start
        == 5
    )

    assert (
        ranges[
            "worship.opening_songs[0]"
        ].start
        == 6
    )

    assert (
        ranges[
            "worship.scripture"
        ].start
        == 10
    )

    assert (
        ranges[
            "worship.scripture"
        ].end
        == 11
    )

    assert (
        ranges[
            "transition:"
            "worship.scripture"
            "->end"
        ].start
        == 12
    )
