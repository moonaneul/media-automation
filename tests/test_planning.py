from pathlib import Path

import pytest

from media_automation.planning import (
    BlockKind,
    IncompletePlanError,
    build_wednesday_plan,
)
from media_automation.weekly_data.loader import load_yaml
from media_automation.weekly_data.models import (
    WednesdayData,
    parse_weekly_data,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples" / "weekly"


def load_wednesday() -> WednesdayData:
    raw = load_yaml(
        SAMPLES / "wednesday.example.yaml"
    )

    data = parse_weekly_data(raw)

    assert isinstance(data, WednesdayData)

    return data


def test_wednesday_plan_order():
    data = load_wednesday()

    plan = build_wednesday_plan(data)

    assert [block.key for block in plan] == [
        "pre_service",

        "opening_songs[0]",
        "transition:opening_songs[0]->opening_songs[1]",

        "opening_songs[1]",
        "transition:opening_songs[1]->opening_songs[2]",

        "opening_songs[2]",
        "transition:opening_songs[2]->prayer",

        "prayer",
        "transition:prayer->additional_song",

        "additional_song",
        "transition:additional_song->scripture",

        "scripture",
        "transition:scripture->sermon_title",

        "sermon_title",
        "transition:sermon_title->additional_scripture",

        "additional_scripture",
        "transition:additional_scripture->decision_hymn",

        "decision_hymn",
    ]


def test_transition_blocks_are_blank():
    data = load_wednesday()

    plan = build_wednesday_plan(data)

    transition_blocks = [
        block
        for block in plan
        if block.key.startswith("transition:")
    ]

    assert transition_blocks

    assert all(
        block.kind == BlockKind.BLANK
        for block in transition_blocks
    )


def test_none_additional_scripture_is_skipped():
    raw = load_yaml(
        SAMPLES / "wednesday.example.yaml"
    )

    raw["additional_scripture"] = {
        "status": "NONE",
    }

    data = parse_weekly_data(raw)

    assert isinstance(data, WednesdayData)

    plan = build_wednesday_plan(data)

    keys = [block.key for block in plan]

    assert "additional_scripture" not in keys

    assert (
        "transition:sermon_title->decision_hymn"
        in keys
    )


def test_unset_additional_scripture_stops_planning():
    raw = load_yaml(
        SAMPLES / "wednesday.example.yaml"
    )

    raw["additional_scripture"] = {
        "status": "UNSET",
    }

    data = parse_weekly_data(raw)

    assert isinstance(data, WednesdayData)

    with pytest.raises(
        IncompletePlanError,
        match="additional_scripture",
    ):
        build_wednesday_plan(data)


def test_scripture_is_single_plan_block():
    """
    본문 범위가 여러 절이어도 Planning 단계에서는
    Scripture 블록 하나만 만든다.

    절별 슬라이드 분리는 PPT 생성 단계의 책임이다.
    """

    data = load_wednesday()

    plan = build_wednesday_plan(data)

    scripture_blocks = [
        block
        for block in plan
        if block.key == "scripture"
    ]

    assert len(scripture_blocks) == 1

    assert (
        scripture_blocks[0].kind
        == BlockKind.SCRIPTURE
    )