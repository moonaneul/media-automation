"""UI regression: explicit song lookup, no auto-run whole-library imports."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'src/media_automation/web/original/ui'


def test_one_drive_lookup_is_primary_and_advanced_import_is_collapsed():
    html = (UI / 'index.html').read_text()
    assert '<h1>OneDrive 원본 찾기</h1>' in html
    assert html.count('id="cloud-library-search"') == 1
    assert html.count('id="cloud-library-list"') == 1
    assert 'id="library-catalog-details"' in html
    assert 'id="cloud-library-tools"' in html
    assert '<summary>전체 OneDrive 원본 연결 관리' in html
    assert 'CloudMedia.autoConnect().catch' not in html


def test_navigating_library_never_triggers_mutating_auto_connect():
    js = (UI / 'onedrive.js').read_text()
    assert 'const query=el(\'library-search\').value.trim();if(!query)' in js
    assert 'if(b.dataset.page===\'library\')refresh()' in js
    assert "if(e.target.value==='library')refresh()" in js
    assert "if(confirm('OneDrive 전체 원본을 검색하고" in js
    assert "if(b.dataset.page==='library')autoConnect()" not in js
    assert "else if(e.target.value==='library')autoConnect()" not in js
