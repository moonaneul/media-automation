from pathlib import Path

import yaml
from pptx import Presentation

from media_automation.bible import (
    BiblePassage,
    BibleVerse,
    InMemoryBibleProvider,
)
from media_automation.planning import (
    build_friday_zoom_plan,
)
from media_automation.ppt import (
    build_friday_zoom_structure,
)
from media_automation.weekly_data.models import (
    FridayZoomData,
    parse_weekly_data,
)


ROOT = Path(__file__).resolve().parents[1]


def load_weekly(
    filename: str,
) -> FridayZoomData:
    path = (
        ROOT
        / "samples"
        / "weekly"
        / filename
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    weekly = parse_weekly_data(raw)

    assert isinstance(
        weekly,
        FridayZoomData,
    )

    return weekly


def load_bible(
    filename: str,
) -> InMemoryBibleProvider:
    path = (
        ROOT
        / "samples"
        / "weekly"
        / filename
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    passages = {}

    for lookup_reference, data in (
        raw["passages"].items()
    ):
        verses = tuple(
            BibleVerse(
                number=int(number),
                text=text,
            )
            for number, text
            in data["verses"].items()
        )

        passages[
            lookup_reference
        ] = BiblePassage(
            reference=data["reference"],
            verses=verses,
        )

    return InMemoryBibleProvider(
        passages
    )


def test_20260911_structure_matches_real_ppt(
    tmp_path,
):
    weekly = load_weekly(
        "friday-zoom-20260911.yaml"
    )

    bible = load_bible(
        "friday-zoom-20260911-bible.yaml"
    )

    plan = build_friday_zoom_plan(
        weekly
    )

    output = (
        tmp_path
        / "20260911.pptx"
    )

    result = build_friday_zoom_structure(
        plan,
        output,
        bible_provider=bible,
    )

    prs = Presentation(output)

    assert len(prs.slides) == 18

    ranges = result.slide_ranges

    assert ranges["pre_service"].start == 1
    assert ranges["opening_songs[0]"].start == 2
    assert ranges["opening_songs[1]"].start == 3
    assert ranges["first_prayer"].start == 4
    assert ranges["song_after_prayer"].start == 5

    assert ranges["scripture"].start == 6
    assert ranges["scripture"].end == 11

    assert ranges["sermon_title"].start == 12

    assert (
        ranges[
            "additional_scripture"
        ].start
        == 13
    )

    assert ranges["response_song"].start == 14
    assert ranges["word_prayer"].start == 15
    assert ranges["intercession_song"].start == 16
    assert ranges["community_prayer"].start == 17
    assert ranges["personal_prayer"].start == 18


def test_20260918_structure_matches_real_ppt(
    tmp_path,
):
    weekly = load_weekly(
        "friday-zoom-20260918.yaml"
    )

    bible = load_bible(
        "friday-zoom-20260918-bible.yaml"
    )

    plan = build_friday_zoom_plan(
        weekly
    )

    output = (
        tmp_path
        / "20260918.pptx"
    )

    result = build_friday_zoom_structure(
        plan,
        output,
        bible_provider=bible,
    )

    prs = Presentation(output)

    assert len(prs.slides) == 17

    ranges = result.slide_ranges

    assert ranges["pre_service"].start == 1
    assert ranges["opening_songs[0]"].start == 2
    assert ranges["opening_songs[1]"].start == 3
    assert ranges["first_prayer"].start == 4
    assert ranges["song_after_prayer"].start == 5

    assert ranges["scripture"].start == 6
    assert ranges["scripture"].end == 11

    assert ranges["sermon_title"].start == 12

    assert (
        "additional_scripture"
        not in ranges
    )

    assert ranges["response_song"].start == 13
    assert ranges["word_prayer"].start == 14
    assert ranges["intercession_song"].start == 15
    assert ranges["community_prayer"].start == 16
    assert ranges["personal_prayer"].start == 17