"""UI preserves explicit review before importing an HWP bulletin."""
from media_automation.web import blue_original

def test_hwp_upload_shows_review_immediately_without_auto_apply():
    js = blue_original.resource("/blue-original.js")[0].decode("utf-8")
    assert "parse();msg('파일을 읽고 항목을 찾았습니다." in js
    assert "선택 항목 반영" in js
    assert "root.append(note)" in js
    assert "시작 찬양 또는 별도 찬송에 자동 배정하지 않습니다" in js
    assert "function form()" in js
    assert "function parse()" in js
    assert "function renderFridayMode()" in js
