import pytest
from pathlib import Path

from media_automation.weekly_data import (
    ValidationState,
    validate_weekly_file,
)


ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "samples" / "weekly"


def test_wednesday_sample_is_valid():
    result = validate_weekly_file(
        SAMPLES / "wednesday.example.yaml"
    )

    assert result.state == ValidationState.VALID
    assert result.errors == ()


def test_sunday_sample_is_incomplete():
    result = validate_weekly_file(
        SAMPLES / "sunday.example.yaml"
    )

    assert result.state == ValidationState.INCOMPLETE

    assert (
        "worship.additional_scripture"
        in result.unresolved
    )


def test_friday_zoom_sample_is_valid():
    result = validate_weekly_file(
        SAMPLES / "friday-zoom.example.yaml"
    )

    assert result.state == ValidationState.VALID
    assert result.errors == ()


def test_unknown_service_is_invalid(tmp_path):
    sample = tmp_path / "invalid.yaml"

    sample.write_text(
        "service: unknown\n"
        "date: 2026-10-01\n",
        encoding="utf-8",
    )

    result = validate_weekly_file(sample)

    assert result.state == ValidationState.INVALID


def test_invalid_status_is_invalid(tmp_path):
    sample = tmp_path / "invalid-status.yaml"

    sample.write_text(
        """
service: wednesday
date: 2026-10-07

opening_songs:
  - status: WRONG
    title: song1
  - status: VALUE
    title: song2
  - status: VALUE
    title: song3

prayer:
  status: VALUE
  person: tester

additional_song:
  status: VALUE
  title: song4

scripture:
  status: VALUE
  reference: "요 3:16"

sermon_title:
  status: VALUE
  text: title

additional_scripture:
  status: NONE

decision_hymn:
  status: VALUE
  title: hymn
""",
        encoding="utf-8",
    )

    result = validate_weekly_file(sample)

    assert result.state == ValidationState.INVALID

def test_sunday_requires_bulletin_serving_fields():
    from pydantic import ValidationError

    from media_automation.weekly_data.models import (
        parse_weekly_data,
    )

    data = {
        "service": "sunday",
        "date": "2026-09-27",
        "worship": {
            "opening_songs": [
                {"status": "VALUE", "title": "찬양1"},
                {"status": "VALUE", "title": "찬양2"},
                {"status": "VALUE", "title": "찬양3"},
            ],
            "separate_hymn": {
                "status": "VALUE",
                "title": "찬송",
            },
            "offering_hymn": {
                "status": "VALUE",
                "title": "봉헌찬송",
            },
            "special_song": {
                "status": "NONE",
            },
            "sermon_title": {
                "status": "VALUE",
                "text": "설교 제목",
            },
            "scripture": {
                "status": "VALUE",
                "reference": "히 11:1-3",
            },
            "additional_scripture": {
                "status": "NONE",
            },
            "decision_hymn": {
                "status": "VALUE",
                "title": "결단찬송",
            },
        },
        "serving": {
            "this_week": {
                "first_service": {
                    "prayer": {
                        "status": "VALUE",
                        "person": "인도자",
                    },
                },
                "second_service": {
                    "prayer": {
                        "status": "VALUE",
                        "person": "위윤기",
                    },
                    "offering_prayer": {
                        "status": "VALUE",
                        "person": "문호성",
                    },
                },
                "dishwashing": {
                    "status": "VALUE",
                    "person": "이광민",
                },
            },
            "next_week": {
                "first_service": {
                    "prayer": {
                        "status": "VALUE",
                        "person": "인도자",
                    },
                },
                "second_service": {
                    "prayer": {
                        "status": "VALUE",
                        "person": "문희재",
                    },
                    "offering_prayer": {
                        "status": "VALUE",
                        "person": "장기훈",
                    },
                },
                "dishwashing": {
                    "status": "VALUE",
                    "person": "김진아",
                },
            },
        },
        "bulletin": {
            "number": {
                "status": "VALUE",
                "value": "13-39",
            },
            "church_news": {
                "status": "VALUE",
                "items": [
                    {"text": "교회 소식"},
                ],
            },
            "afternoon_service": {
                "status": "VALUE",
                "title": "생명의 삶 3주차",
            },
            "monthly_schedule": {
                "status": "VALUE",
                "items": [
                    {
                        "date": "2026-09-06",
                        "content": "집사 부부 모임",
                    },
                ],
            },
            "cell_group": {
                "status": "VALUE",
                "scripture": "히 11:1-3",
                "title": "살아 있는 믿음",
                "questions": [
                    "질문1",
                    "질문2",
                    "질문3",
                    "질문4",
                ],
            },
        },
    }

    with pytest.raises(ValidationError):
        parse_weekly_data(data)



def test_monthly_schedule_can_preserve_date_range():
    from media_automation.weekly_data.models import (
        ScheduleItem,
    )

    item = ScheduleItem(
        display_date="9/24(목)~26(토)",
        content="추석 연휴",
    )

    assert item.date is None
    assert (
        item.display_date
        == "9/24(목)~26(토)"
    )
    assert item.content == "추석 연휴"


def test_person_field_can_preserve_title():
    from media_automation.weekly_data.models import (
        PersonField,
        WeeklyStatus,
    )

    person = PersonField(
        status=WeeklyStatus.VALUE,
        person="김한섭",
        title="집사",
    )

    assert person.person == "김한섭"
    assert person.title == "집사"
