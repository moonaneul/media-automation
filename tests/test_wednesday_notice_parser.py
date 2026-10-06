from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "parse_wednesday_notice.py"
)

spec = spec_from_file_location("parse_wednesday_notice", PARSER_PATH)
module = module_from_spec(spec)
assert spec is not None
assert spec.loader is not None
spec.loader.exec_module(module)

parse_notice = module.parse_notice


def test_wednesday_notice_distinguishes_blank_and_missing():
    text = (
        "날짜: 2026-10-07\n"
        "찬양1: 첫 곡\n"
        "찬양2: 둘째 곡\n"
        "찬양3: 셋째 곡\n"
        "기도: 한송희\n"
        "추가 찬양: 네번째 곡\n"
        "본문: 삼상 17:41~49\n"
        "설교 제목: 골리앗 앞에 서는 믿음\n"
        "읽을 말씀:\n"
        "결단 찬송: 나는 믿네\n"
    )

    data, unknown = parse_notice(text)

    assert data["additional_scripture"]["status"] == "blank"
    assert data["additional_scripture"]["value"] is None
    assert data["decision_hymn"]["status"] == "provided"
    assert unknown == []


def test_missing_field_remains_missing():
    data, unknown = parse_notice("날짜: 2026-10-07\n기도: 한송희\n")

    assert data["opening_song_1"]["status"] == "missing"
    assert data["scripture"]["status"] == "missing"
    assert unknown == []


def test_known_non_slide_fields_do_not_require_review():
    text = (
        "날짜: 2026-10-07\n"
        "광고: 이번 주 광고\n"
        "폐회기도: 이은철\n"
        "찬양 담당: 이하은\n"
    )

    _, unknown = parse_notice(text)

    assert unknown == []


def test_unknown_sentence_requires_review():
    _, unknown = parse_notice(
        "날짜: 2026-10-07\n"
        "이 문장은 어떤 항목인지 알 수 없음\n"
    )

    assert unknown == ["이 문장은 어떤 항목인지 알 수 없음"]


def test_prayer_parentheses_form_is_supported():
    data, unknown = parse_notice(
        "날짜: 2026-10-07\n"
        "기도(한송희)\n"
    )

    assert data["prayer"]["status"] == "provided"
    assert data["prayer"]["value"] == "한송희"
    assert unknown == []


def test_opening_song_count_creates_asset_backed_slots():
    data, unknown = parse_notice(
        "날짜: 2026-10-07\n"
        "찬양3(이하은)\n"
        "기도: 한송희\n"
    )

    assert [
        data[f"opening_song_{index}"]["status"]
        for index in (1, 2, 3)
    ] == ["asset_required", "asset_required", "asset_required"]
    assert data["opening_song_1"]["leader"] == "이하은"
    assert unknown == []


def test_song_count_after_prayer_means_additional_song():
    data, unknown = parse_notice(
        "날짜: 2026-10-07\n"
        "찬양3(이하은)\n"
        "기도: 한송희\n"
        "찬양1\n"
    )

    assert data["additional_song"]["status"] == "asset_required"
    assert unknown == []
