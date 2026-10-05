from pathlib import Path

import yaml

from media_automation.planning import (
    build_friday_zoom_plan,
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


def test_20260918_friday_zoom_structure():
    weekly = load_weekly(
        "friday-zoom-20260918.yaml"
    )

    plan = build_friday_zoom_plan(
        weekly
    )

    assert len(plan) == 12

    assert [
        block.key
        for block in plan
    ] == [
        "pre_service",
        "opening_songs[0]",
        "opening_songs[1]",
        "first_prayer",
        "song_after_prayer",
        "scripture",
        "sermon_title",
        "response_song",
        "word_prayer",
        "intercession_song",
        "community_prayer",
        "personal_prayer",
    ]

    scripture_references = [
        block.value.reference
        for block in plan
        if hasattr(
            block.value,
            "reference",
        )
    ]

    assert scripture_references == [
        "왕상 9:1-10",
    ]


def test_20260911_friday_zoom_structure():
    weekly = load_weekly(
        "friday-zoom-20260911.yaml"
    )

    plan = build_friday_zoom_plan(
        weekly
    )

    assert len(plan) == 13

    assert [
        block.key
        for block in plan
    ] == [
        "pre_service",
        "opening_songs[0]",
        "opening_songs[1]",
        "first_prayer",
        "song_after_prayer",
        "scripture",
        "sermon_title",
        "additional_scripture",
        "response_song",
        "word_prayer",
        "intercession_song",
        "community_prayer",
        "personal_prayer",
    ]

    scripture_references = [
        block.value.reference
        for block in plan
        if hasattr(
            block.value,
            "reference",
        )
    ]

    assert scripture_references == [
        "민 21:1-9",
        "요 3:14-15",
    ]
def test_20260904_friday_zoom_structure():
    weekly = load_weekly(
        "friday-zoom-20260904.yaml"
    )

    plan = build_friday_zoom_plan(
        weekly
    )

    assert len(plan) == 12

    assert [
        block.key
        for block in plan
    ] == [
        "pre_service",
        "opening_songs[0]",
        "opening_songs[1]",
        "first_prayer",
        "song_after_prayer",
        "scripture",
        "sermon_title",
        "response_song",
        "word_prayer",
        "intercession_song",
        "community_prayer",
        "personal_prayer",
    ]

    scripture_references = [
        block.value.reference
        for block in plan
        if hasattr(
            block.value,
            "reference",
        )
    ]

    assert scripture_references == [
        "창 29:15-30",
    ]