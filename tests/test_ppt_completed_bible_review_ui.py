"""An already-reviewed PPT must not demand another Bible review dialog.

User-provided, not independently validated Bible JSON stays unverified. Only
an actual person can acknowledge manual verse-by-verse review in this flow.
"""
from pathlib import Path

from media_automation.web.original import bible_connection


UI=Path("src/media_automation/web/original/ui/index.html")


def test_existing_ppt_review_is_identified_as_saved_history_and_can_be_rechecked():
    script=UI.read_text(encoding="utf-8")
    assert "$('complete').disabled=!o.fileId||!!o.changed||(pdf&&!!o.complete);" in script
    assert "PPT 다시 검수" in script
    assert "id=\"ppt-review-cancel\"" in script
    assert "이번 화면에서 새로 검수했다는 뜻은 아닙니다." in script


def test_manual_confirmation_is_not_mislabelled_as_auto_scripture_validation():
    script=UI.read_text(encoding="utf-8")
    assert "confirmedManualReviews" in script
    assert "수동 성경 대조 확인 기록됨 (자동 검증 아님)" in script
    assert "confirmed_manual_reviews:manualReview" in script
    assert "성경 본문의 자동 검증이 완료되지 않았습니다." in script
    assert "실제 화면의 모든 절을 개역개정과 직접 대조" in script


def test_unvalidated_json_never_claims_automatic_bible_review(tmp_path):
    from media_automation.web.original.bible_connection import resolve
    import json
    bible=tmp_path/"passages.json"
    bible.write_text(json.dumps({"창 1:1":"태초에 하나님이 천지를 창조하시니라"},ensure_ascii=False))
    result=resolve([{"kind":"input","state":"VALUE","key":"성경 본문","content":"창 1:1"}],
                   source_dir=tmp_path,provided_file=bible)
    assert result["성경 본문"]["text_review_pending"] is True
    assert result["성경 본문"]["source_validated"] is False
