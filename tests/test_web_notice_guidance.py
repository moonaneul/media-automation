"""UI imports reliable Sunday fields while retaining review for ambiguous items."""
from media_automation.web import blue_original

def test_hwp_upload_uses_guarded_sunday_import_and_keeps_review_guidance():
    js = blue_original.resource("/blue-original.js")[0].decode("utf-8")
    assert "parse();if(service==='sunday'&&/\\.hwp$/i.test(f.name)){autoApplySundayHwp();}" in js
    assert "SundayHwpAutofill.plan(" in js
    assert "if(policy.dateMismatch)" in js
    assert "선택 항목 반영" in js
    assert "root.append(note)" in js
    assert "시작 찬양 또는 별도 찬송에 자동 배정하지 않습니다" in js
    assert "function form()" in js
    assert "function parse()" in js
    assert "function renderFridayMode()" in js
