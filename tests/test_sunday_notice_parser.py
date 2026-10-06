from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


PARSER_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "parse_sunday_notice.py"
)

spec = spec_from_file_location("parse_sunday_notice", PARSER_PATH)
module = module_from_spec(spec)
assert spec is not None
assert spec.loader is not None
spec.loader.exec_module(module)

parse_notice = module.parse_notice
build_bible_requests = module.build_bible_requests
build_song_checklist = module.build_song_checklist


def test_sunday_notice_distinguishes_blank_and_missing():
    text = (
        "날짜: 2026-10-11\n"
        "찬양1: 첫 곡\n"
        "찬양2: 둘째 곡\n"
        "찬양3: 셋째 곡\n"
        "별도 찬송: 96장 예수님은 누구신가\n"
        "2부 기도: 김철수\n"
        "교회 소식: 있음\n"
        "봉헌 찬송: 50장\n"
        "2부 봉헌기도: 이영희\n"
        "특송:\n"
        "설교 제목: 예시 설교\n"
        "본문: 롬 5:6~11\n"
        "읽을 말씀:\n"
        "결단 찬송: 315장\n"
    )

    data, unknown = parse_notice(text)

    assert data["special_song"]["status"] == "blank"
    assert data["additional_scripture"]["status"] == "blank"
    assert data["second_service_prayer"]["value"] == "김철수"
    assert data["second_service_offering_prayer"]["value"] == "이영희"
    assert data["decision_hymn"]["status"] == "provided"
    assert unknown == []


def test_missing_field_remains_missing():
    data, unknown = parse_notice(
        "날짜: 2026-10-11\n"
        "2부 기도: 김철수\n"
    )

    assert data["opening_song_1"]["status"] == "missing"
    assert data["scripture"]["status"] == "missing"
    assert data["second_service_offering_prayer"]["status"] == "missing"
    assert unknown == []


def test_first_service_people_are_not_used_for_second_service():
    text = (
        "날짜: 2026-10-11\n"
        "1부 기도: 1부기도자\n"
        "1부 봉헌기도: 1부봉헌기도자\n"
        "2부 기도: 2부기도자\n"
        "2부 봉헌기도: 2부봉헌기도자\n"
    )

    data, unknown = parse_notice(text)

    assert data["second_service_prayer"]["value"] == "2부기도자"
    assert data["second_service_offering_prayer"]["value"] == "2부봉헌기도자"
    assert unknown == []


def test_parentheses_person_forms_are_supported():
    text = (
        "날짜: 2026-10-11\n"
        "기도(문희재 집사)\n"
        "봉헌기도(문호성 형제)\n"
    )

    data, unknown = parse_notice(text)

    assert data["second_service_prayer"]["value"] == "문희재 집사"
    assert data["second_service_offering_prayer"]["value"] == "문호성 형제"
    assert unknown == []


def test_opening_song_count_creates_three_asset_slots():
    data, unknown = parse_notice(
        "날짜: 2026-10-11\n"
        "찬양3(이하은)\n"
    )

    assert [
        data[f"opening_song_{index}"]["status"]
        for index in (1, 2, 3)
    ] == ["asset_required", "asset_required", "asset_required"]
    assert data["opening_song_1"]["leader"] == "이하은"
    assert unknown == []


def test_unknown_sentence_requires_review():
    _, unknown = parse_notice(
        "날짜: 2026-10-11\n"
        "이 문장은 어떤 항목인지 알 수 없음\n"
    )

    assert unknown == ["이 문장은 어떤 항목인지 알 수 없음"]


def test_bible_requests_include_only_provided_passages():
    data, _ = parse_notice(
        "날짜: 2026-10-11\n"
        "본문: 롬 5:6~11\n"
        "읽을 말씀:\n"
    )

    requests = build_bible_requests(data)["requests"]

    assert requests == [
        {
            "source": "scripture",
            "reference": "롬 5:6~11",
            "translation": "개역개정",
            "display_rule": "세례→침례",
        }
    ]


def test_song_checklist_uses_fixed_sunday_slot_names():
    data, _ = parse_notice(
        "날짜: 2026-10-11\n"
        "찬양3(이하은)\n"
        "별도 찬송: 96장 예수님은 누구신가\n"
        "봉헌 찬송: 50장\n"
        "특송:\n"
        "결단 찬송: 315장\n"
    )

    items = build_song_checklist(data)["items"]

    assert [item["expected_filename"] for item in items] == [
        "opening_song_1.pptx",
        "opening_song_2.pptx",
        "opening_song_3.pptx",
        "separate_hymn.pptx",
        "offering_hymn.pptx",
        "decision_hymn.pptx",
    ]
