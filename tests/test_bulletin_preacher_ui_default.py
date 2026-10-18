"""Sunday bulletin UI should explain fixed church pastor defaults without saving weekly people."""
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "src/media_automation/web/original/ui/index.html"


def test_sunday_preacher_and_leader_use_confirmed_church_setting_labels():
    source=UI.read_text(encoding="utf-8")
    assert "['주일 인도자','설교자'].includes(label)" in source
    assert "기본적으로 교회 설정의 담임목사를 설교자로 표기합니다." in source
    assert "기본: 담임목사 · 다른 설교자일 때만 입력" in source
    assert "담임목사 기본값" in source
    assert "기본값 사용" not in source or "교회 기본값" in source
    # Never write the default pastor to current-week fields just by rendering.
    assert 'record().fields["설교자"]=value' not in source
