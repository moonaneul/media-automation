from pathlib import Path

import pytest

from media_automation.planning import (
    BlockKind,
    IncompletePlanError,
    build_friday_zoom_plan,
    build_sunday_plan,
    build_wednesday_plan,
)
from media_automation.weekly_data.loader import load_yaml
from media_automation.weekly_data.models import (
    FridayZoomData,
    SundayData,
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

def load_sunday_with_no_additional_scripture() -> SundayData:
    raw = load_yaml(
        SAMPLES / "sunday.example.yaml"
    )

# 샘플은 UNSET 상태이므로,
# 전체 순서 테스트에서는 이번 주에 추가 말씀이 없다고 확정한다.
    raw["worship"]["additional_scripture"] = {
        "status": "NONE",
    }

    data = parse_weekly_data(raw)

    assert isinstance(data, SundayData)

    return data


def test_sunday_plan_order():
    data = load_sunday_with_no_additional_scripture()

    plan = build_sunday_plan(data)

    content_keys = [
        block.key
        for block in plan
        if block.kind != BlockKind.BLANK
    ]

    assert content_keys == [
        "pre_service",
        "worship.opening_songs[0]",
        "worship.opening_songs[1]",
        "worship.opening_songs[2]",
        "worship.separate_hymn",
        "serving.this_week.second_service.prayer",
        "bulletin.church_news",
        "worship.offering_hymn",
        "serving.this_week.second_service.offering_prayer",
        "worship.sermon_title",
        "worship.scripture",
        "worship.decision_hymn",
    ]


def test_sunday_special_song_none_is_skipped():
    data = load_sunday_with_no_additional_scripture()

    plan = build_sunday_plan(data)

    keys = [block.key for block in plan]

    assert "worship.special_song" not in keys


def test_sunday_church_news_has_own_block_kind():
    data = load_sunday_with_no_additional_scripture()

    plan = build_sunday_plan(data)

    church_news = next(
        block
        for block in plan
        if block.key == "bulletin.church_news"
    )

    assert church_news.kind == BlockKind.CHURCH_NEWS


def test_sunday_uses_second_service_prayer():
    data = load_sunday_with_no_additional_scripture()

    plan = build_sunday_plan(data)

    prayer = next(
        block
        for block in plan
        if (
            block.key
            == "serving.this_week.second_service.prayer"
        )
    )

    assert prayer.value.person == "김철수"


def test_sunday_unset_additional_scripture_stops_planning():
    raw = load_yaml(
        SAMPLES / "sunday.example.yaml"
    )

    data = parse_weekly_data(raw)

    assert isinstance(data, SundayData)

    with pytest.raises(
        IncompletePlanError,
        match="worship.additional_scripture",
    ):
        build_sunday_plan(data)

def load_friday_zoom() -> FridayZoomData:
    raw = load_yaml(
        SAMPLES / "friday-zoom.example.yaml"
    )

    data = parse_weekly_data(raw)

    assert isinstance(data, FridayZoomData)

    return data


def test_friday_zoom_plan_order():
    data = load_friday_zoom()

    plan = build_friday_zoom_plan(data)

    content_keys = [
        block.key
        for block in plan
        if block.kind != BlockKind.BLANK
    ]

    assert content_keys == [
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


def test_friday_zoom_songs_use_zoom_song_kind():
    data = load_friday_zoom()

    plan = build_friday_zoom_plan(data)

    song_keys = {
        "opening_songs[0]",
        "opening_songs[1]",
        "song_after_prayer",
        "response_song",
        "intercession_song",
    }

    song_blocks = [
        block
        for block in plan
        if block.key in song_keys
    ]

    assert len(song_blocks) == 5

    assert all(
        block.kind == BlockKind.ZOOM_SONG
        for block in song_blocks
    )


def test_friday_zoom_prayer_topics_have_own_kind():
    data = load_friday_zoom()

    plan = build_friday_zoom_plan(data)

    prayer_keys = {
        "first_prayer",
        "word_prayer",
        "community_prayer",
    }

    prayer_blocks = [
        block
        for block in plan
        if block.key in prayer_keys
    ]

    assert len(prayer_blocks) == 3

    assert all(
        block.kind == BlockKind.PRAYER_TOPICS
        for block in prayer_blocks
    )


def test_friday_zoom_additional_scripture_none_is_skipped():
    data = load_friday_zoom()

    plan = build_friday_zoom_plan(data)

    keys = [block.key for block in plan]

    assert "additional_scripture" not in keys

    assert (
        "transition:sermon_title->response_song"
        in keys
    )


def test_friday_zoom_unset_stops_planning():
    raw = load_yaml(
        SAMPLES / "friday-zoom.example.yaml"
    )

    raw["word_prayer"] = {
        "status": "UNSET",
    }

    data = parse_weekly_data(raw)

    assert isinstance(data, FridayZoomData)

    with pytest.raises(
        IncompletePlanError,
        match="word_prayer",
    ):
        build_friday_zoom_plan(data)

from media_automation.planning import (
    BlockKind,
    SermonTitleContent,
)
from media_automation.planning.planner import (
    IncompletePlanError,
    _make_sermon_title_block,
)
from media_automation.weekly_data.models import (
    ScriptureField,
    TextField,
)


def test_sermon_title_block_contains_title_and_scripture_reference():
    block = _make_sermon_title_block(
        title_field=TextField(
            status="VALUE",
            text="외모와 중심",
        ),
        scripture_field=ScriptureField(
            status="VALUE",
            reference="삼상 16:6-7",
        ),
        key="sermon_title",
    )

    assert block is not None
    assert (
        block.kind
        == BlockKind.SERMON_TITLE
    )

    assert isinstance(
        block.value,
        SermonTitleContent,
    )

    assert (
        block.value.title
        == "외모와 중심"
    )

    assert (
        block.value.scripture_reference
        == "삼상 16:6-7"
    )


def test_sermon_title_unset_is_incomplete():
    with pytest.raises(
        IncompletePlanError
    ):
        _make_sermon_title_block(
            title_field=TextField(
                status="UNSET",
            ),
            scripture_field=ScriptureField(
                status="VALUE",
                reference="삼상 16:6-7",
            ),
            key="sermon_title",
        )


def test_sermon_title_requires_confirmed_scripture():
    with pytest.raises(
        IncompletePlanError
    ):
        _make_sermon_title_block(
            title_field=TextField(
                status="VALUE",
                text="외모와 중심",
            ),
            scripture_field=ScriptureField(
                status="UNSET",
            ),
            key="sermon_title",
        )


def test_sermon_title_rejects_none_scripture():
    with pytest.raises(
        ValueError,
        match="대표 본문",
    ):
        _make_sermon_title_block(
            title_field=TextField(
                status="VALUE",
                text="외모와 중심",
            ),
            scripture_field=ScriptureField(
                status="NONE",
            ),
            key="sermon_title",
        )