"""Regression contract for safe Sunday HWP autofill in original blue interface."""
from media_automation.web import blue_original


def test_original_blue_remains_intact_with_guided_auto_import():
    page=blue_original.page().decode("utf-8")
    assert 'id="form-groups"' in page
    assert 'id="notice-text"' in page
    assert 'id="parse-notice"' in page
    assert 'src="/sunday-hwp-autofill.js"' in page
    policy=blue_original.resource("/sunday-hwp-autofill.js")[0].decode()
    script=blue_original.resource("/blue-original.js")[0].decode()
    assert "isTableReview" in policy
    assert "dateMismatch" in policy
    assert "autoApplySundayHwp()" in script
    assert "r.noticeImportSummary" in script
    assert "function renderFridayMode()" in script
    assert "function form()" in script


def test_original_blue_script_contains_guarded_autofill():
    script=blue_original.resource("/blue-original.js")[0].decode()
    assert "기존 입력 보존" in script
    assert "섬김표 후보 확인" in script
    assert "주보 HWP에서" in script
    assert "r.noticeSongList" in script
