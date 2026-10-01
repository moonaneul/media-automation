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