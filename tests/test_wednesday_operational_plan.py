from pathlib import Path

from media_automation.planning import BlockKind
from media_automation.planning.wednesday_operational import (
    build_wednesday_operational_plan,
)
from media_automation.weekly_data.loader import load_yaml
from media_automation.weekly_data.models import (
    WednesdayData,
    parse_weekly_data,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples" / "weekly" / "wednesday.example.yaml"


def load_wednesday() -> WednesdayData:
    data = parse_weekly_data(load_yaml(SAMPLE))
    assert isinstance(data, WednesdayData)
    return data


def test_operational_plan_keeps_blank_after_pre_service():
    plan = build_wednesday_operational_plan(load_wednesday())

    assert plan[0].kind == BlockKind.PRE_SERVICE
    assert plan[1].kind == BlockKind.BLANK
    assert plan[1].key == "transition:pre_service->opening_songs[0]"
    assert plan[2].key == "opening_songs[0]"


def test_operational_plan_keeps_blank_between_scripture_and_sermon():
    plan = build_wednesday_operational_plan(load_wednesday())
    keys = [block.key for block in plan]

    scripture_index = keys.index("scripture")
    assert keys[scripture_index + 1] == "transition:scripture->sermon_title"
    assert keys[scripture_index + 2] == "sermon_title"


def test_operational_plan_does_not_add_blank_between_scripture_verses():
    plan = build_wednesday_operational_plan(load_wednesday())

    scripture_blocks = [block for block in plan if block.key == "scripture"]
    assert len(scripture_blocks) == 1
