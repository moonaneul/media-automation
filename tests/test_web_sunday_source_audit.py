"""Sunday progress states distinguish absent weekly notice from extraction failures."""
from media_automation.web import blue_original


def test_progress_uses_input_presence_not_parser_success_rate():
    js = blue_original.resource("/blue-original.js")[0].decode("utf-8")
    assert "function updateSundayInputSourceExplanation()" in js
    assert "function renderInputProgress()" in js
    assert "updateSundayInputSourceExplanation();" in js
    assert "별도 주일예배 안내가 필요한 미입력" in js
    assert "섬김표 원본 대조" in js
    assert "○는 인식 실패만을 의미하지 않습니다" in js
    assert "25 / 37" not in js
    assert "' / '+total+' 입력상태'" in js
    assert 'id="form-groups"' in blue_original.page().decode("utf-8")
