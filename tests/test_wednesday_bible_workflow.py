from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "manage_wednesday_bible.py"
)

spec = spec_from_file_location("manage_wednesday_bible", SCRIPT)
module = module_from_spec(spec)
assert spec is not None
assert spec.loader is not None
spec.loader.exec_module(module)

expected_verse_numbers = module.expected_verse_numbers
validate_input_payload = module.validate_input_payload


def test_expected_verse_numbers_single_verse():
    assert expected_verse_numbers("요 3:16") == [16]


def test_expected_verse_numbers_range():
    assert expected_verse_numbers("삼상 17:41~49") == list(range(41, 50))


def test_validate_input_payload_accepts_complete_passage():
    payload = {
        "translation": "개역개정",
        "passages": {
            "삼상 17:41~43": {
                "reference": "삼상 17:41~43",
                "verses": {
                    41: "첫째 절 본문",
                    42: "둘째 절 본문",
                    43: "셋째 절 본문",
                },
            }
        },
    }

    clean = validate_input_payload(payload)

    assert clean["translation"] == "개역개정"
    assert clean["validated"] is True
    assert list(clean["passages"]["삼상 17:41~43"]["verses"]) == [41, 42, 43]


def test_validate_input_payload_rejects_wrong_translation():
    payload = {
        "translation": "개역한글",
        "passages": {
            "요 3:16": {
                "reference": "요 3:16",
                "verses": {16: "본문"},
            }
        },
    }

    with pytest.raises(ValueError, match="개역개정"):
        validate_input_payload(payload)


def test_validate_input_payload_rejects_missing_verse():
    payload = {
        "translation": "개역개정",
        "passages": {
            "삼상 17:41~43": {
                "reference": "삼상 17:41~43",
                "verses": {
                    41: "첫째 절",
                    43: "셋째 절",
                },
            }
        },
    }

    with pytest.raises(ValueError, match="절 번호"):
        validate_input_payload(payload)


def test_validate_input_payload_rejects_blank_text():
    payload = {
        "translation": "개역개정",
        "passages": {
            "요 3:16": {
                "reference": "요 3:16",
                "verses": {16: ""},
            }
        },
    }

    with pytest.raises(ValueError, match="본문이 비어"):
        validate_input_payload(payload)
