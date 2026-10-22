"""The interface is a weekly production tool, not a remote archive manager.

These checks preserve the service personnel in weekly inputs while removing
only the optional media-team creator tracking controls.
"""
from pathlib import Path


UI = Path("src/media_automation/web/original/ui")


def test_media_creator_controls_removed_without_hiding_worship_roles():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'id="person"' not in html
    assert 'id="team-names"' not in html
    assert 'id="save-names"' not in html
    assert "function renderPeople()" not in html
    assert "renderPeople();" not in html
    assert "$('person').onchange" not in html
    assert "$('save-names').onclick" not in html
    # Service prayer/serving personnel are required for weekly PPT/bulletins.
    assert "'기도 담당자'" in html
    assert "'2부 기도 담당자'" in html
    assert "'이번 주 설거지'" in html
    assert 'id="friday-mode"' in html or "select.id='friday-mode'" in html


def test_rare_storage_paths_and_history_collapsed_with_existing_connectors():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert 'id="storage-advanced"' in html
    assert '<summary>원본·완료본 폴더 변경</summary>' in html
    assert '<details class="panel archive-history" id="archive-history" hidden>' in html
    assert 'id="cloud-shared-archive_sunday_pdf-link"' in html
    assert 'id="cloud-shared-archive_sunday_ppt-link"' in html
    assert 'id="cloud-shared-archive_wednesday-link"' in html
    assert 'id="cloud-shared-archive_friday-link"' in html
    assert 'id="cloud-connect"' in html
    # No secrets, hardcoded tenant paths, or destructive cloud file actions.
    assert 'type="password" autocomplete="new-password"' in html
    assert 'id="cloud-disconnect"' in html
    assert '<button data-page="archive" hidden>찬양 자료실</button>' in html
    assert '<option value="archive" hidden>찬양 자료실</option>' in html
    assert '#archive-page{display:none!important}' in html


def test_archive_source_search_does_not_collapse_on_narrow_windows():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert '#archive-page .search-row{display:grid;grid-template-columns:minmax(220px,1fr)' in html
    assert '#archive-page .search-row input,#archive-page .search-row select{width:100%;min-width:0;max-width:100%;flex:none}' in html
    assert '@media(max-width:860px){#archive-page .search-row{' in html
    assert '@media(max-width:560px){#archive-page .search-row{' in html


def test_historic_cloud_listing_requires_explicit_opt_in():
    js = (UI / "onedrive.js").read_text(encoding="utf-8")
    assert "el('archive-history').addEventListener('toggle'" in js
    assert "if(el('archive-history').open)archives(" in js
    assert "if(b.dataset.page==='archive')archives();" not in js
    assert "if(e.target.value==='archive')archives();" not in js
    assert "el('cloud-archive-refresh').onclick" in js
    # Reading remote metadata does not download historical files.
    section = js.split(" async function archives(", 1)[1].split(
        " async function archiveCurrent(", 1
    )[0]
    assert "await api(query)" in section
    assert "api('download'" not in section
