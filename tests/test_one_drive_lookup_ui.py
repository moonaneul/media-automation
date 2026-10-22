"""UI regression: explicit song lookup, no auto-run whole-library imports."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / 'src/media_automation/web/original/ui'


def test_one_drive_lookup_is_primary_and_advanced_import_is_collapsed():
    html = (UI / 'index.html').read_text(encoding='utf-8')
    assert '<h1>OneDrive 원본 찾기</h1>' in html
    assert html.count('id="cloud-library-search"') == 1
    assert html.count('id="cloud-library-list"') == 1
    assert 'id="library-catalog-details"' in html
    assert 'id="cloud-library-tools"' in html
    assert '<summary>전체 OneDrive 원본 연결 관리' in html
    assert 'CloudMedia.autoConnect().catch' not in html


def test_navigating_library_never_triggers_mutating_auto_connect():
    js = (UI / 'onedrive.js').read_text(encoding='utf-8')
    assert 'const query=el(\'library-search\').value.trim();if(!query)' in js
    assert 'if(b.dataset.page===\'library\')refresh()' in js
    assert "if(e.target.value==='library')refresh()" in js
    assert "if(confirm('OneDrive 전체 원본을 검색하고" in js
    assert "if(b.dataset.page==='library')autoConnect()" not in js
    assert "else if(e.target.value==='library')autoConnect()" not in js


def test_production_navigation_hides_catalog_archive_but_preserves_song_source_lookup():
    """The app is a production tool, not a secondary song-file browser."""
    html = (UI / 'index.html').read_text(encoding='utf-8')
    assert '<button data-page="archive" hidden>찬양 자료실</button>' in html
    assert '<option value="archive" hidden>찬양 자료실</option>' in html
    assert '<section id="archive-page" hidden>' in html
    assert '#archive-page{display:none!important}' in html

    # Concealing the old catalog must not remove production-time source selection.
    assert 'id="cloud-library-search"' in html
    assert 'id="cloud-library-list"' in html
    assert 'id="library-catalog-details"' in html
    assert 'id="storage-advanced"' in html
    assert '<button data-page="work" class="active">' in html
    assert '<button data-page="settings">' in html
