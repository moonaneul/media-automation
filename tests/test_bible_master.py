import pytest

from media_automation.bible.master import (
    extract_same_chapter_passage,
    normalize_book,
    parse_reference,
)


def sample_master():
    return {
        "translation": "개역개정",
        "validated": True,
        "books": {
            "사무엘상": {
                17: {
                    41: "사십일절",
                    42: "사십이절",
                    43: "사십삼절",
                }
            },
            "요": {
                3: {
                    16: "십육절",
                }
            },
        },
    }


def test_normalize_book_accepts_full_name_and_abbreviation():
    assert normalize_book("사무엘상") == "삼상"
    assert normalize_book("삼상") == "삼상"


def test_parse_reference_same_chapter_range():
    parsed = parse_reference("삼상 17:41~43")
    assert parsed.book == "삼상"
    assert parsed.chapter == 17
    assert parsed.start_verse == 41
    assert parsed.end_chapter == 17
    assert parsed.end_verse == 43
    assert parsed.crosses_chapters is False


def test_parse_reference_cross_chapter_range_is_detected():
    parsed = parse_reference("마 5:48~6:2")
    assert parsed.crosses_chapters is True


def test_extract_same_chapter_range_from_full_name_master():
    passage = extract_same_chapter_passage(
        sample_master(),
        "삼상 17:41~43",
    )
    assert passage["reference"] == "삼상 17:41~43"
    assert passage["verses"] == {
        41: "사십일절",
        42: "사십이절",
        43: "사십삼절",
    }


def test_extract_single_verse():
    passage = extract_same_chapter_passage(sample_master(), "요 3:16")
    assert passage["verses"] == {16: "십육절"}


def test_extract_rejects_missing_verse():
    with pytest.raises(KeyError, match="절이 없습니다"):
        extract_same_chapter_passage(sample_master(), "삼상 17:41~44")


def test_extract_rejects_cross_chapter_until_ppt_model_supports_it():
    master = {
        "translation": "개역개정",
        "validated": True,
        "books": {
            "마": {
                5: {48: "본문"},
                6: {1: "본문", 2: "본문"},
            }
        },
    }
    with pytest.raises(ValueError, match="장을 넘는"):
        extract_same_chapter_passage(master, "마 5:48~6:2")
