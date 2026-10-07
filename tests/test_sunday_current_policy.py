from pathlib import Path

from media_automation.planning.sunday_policy import (
    SERMON_TO_SCRIPTURE_TRANSITION,
    build_current_sunday_plan,
)
from media_automation.weekly_data.loader import load_yaml
from media_automation.weekly_data.models import SundayData, parse_weekly_data


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples" / "weekly"


def load_sunday() -> SundayData:
    raw = load_yaml(SAMPLES / "sunday.example.yaml")
    raw["worship"]["additional_scripture"] = {
        "status": "NONE",
    }
    data = parse_weekly_data(raw)
    assert isinstance(data, SundayData)
    return data


def test_current_sunday_policy_adds_blank_between_sermon_and_scripture():
    plan = build_current_sunday_plan(load_sunday())
    keys = [block.key for block in plan]

    sermon_index = keys.index("worship.sermon_title")

    assert keys[sermon_index + 1] == SERMON_TO_SCRIPTURE_TRANSITION
    assert keys[sermon_index + 2] == "worship.scripture"
