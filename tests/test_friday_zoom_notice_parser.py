from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "parse_friday_zoom_notice.py"
)

spec = spec_from_file_location(
    "parse_friday_zoom_notice",
    PARSER_PATH,
)

module = module_from_spec(spec)

assert spec is not None
assert spec.loader is not None

spec.loader.exec_module(module)

parse_notice = module.parse_notice


def test_numbered_bullet_prayer_topics():
    text = (
        "\ub0a0\uc9dc: 2026-10-09\n"
        "\uccab \uae30\ub3c4:\n"
        "1. - first topic\n"
        "2) - second topic\n"
        "(3) - third topic\n"
        "\n"
        "\ub9d0\uc500 \uae30\ub3c4:\n"
        "1 - after sermon one\n"
        "2. after sermon two\n"
    )

    data, unknown = parse_notice(text)

    assert data["first_prayer"]["value"] == [
        "first topic",
        "second topic",
        "third topic",
    ]

    assert data["word_prayer"]["value"] == [
        "after sermon one",
        "after sermon two",
    ]

    assert unknown == []


def test_plain_sentence_inside_prayer_requires_review():
    text = (
        "\ub0a0\uc9dc: 2026-10-09\n"
        "\uccab \uae30\ub3c4:\n"
        "- prayer topic\n"
        "ordinary explanatory sentence\n"
    )

    data, unknown = parse_notice(text)

    assert data["first_prayer"]["value"] == [
        "prayer topic"
    ]

    assert unknown == [
        "ordinary explanatory sentence"
    ]
