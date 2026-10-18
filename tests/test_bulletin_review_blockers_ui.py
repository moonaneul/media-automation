"""Review blockers should be actionable without scrolling away from PDF controls."""
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "src/media_automation/web/original/ui/index.html"


def test_pdf_completion_blockers_stay_near_button():
    source = UI.read_text(encoding="utf-8")
    assert 'id="pdf-review-blockers"' in source
    assert "아직 검수 완료로 표시할 수 없습니다. 미확정 항목:" in source
    assert "$('generated-missing')?.scrollIntoView({block:'center'})" not in source
    assert "o.unresolved.join(', ')" in source
