"""The archive view is a remote OneDrive browser, not a local file import.

This checks visible interface copy without touching team files or credentials.
"""
from pathlib import Path


UI = Path("src/media_automation/web/original/ui")


def test_archive_browser_is_not_a_separate_production_screen():
    """Keep inactive DOM targets for older callbacks without exposing archive browsing."""
    html = (UI / "index.html").read_text(encoding="utf-8")
    section = html.split('<section id="archive-page" hidden>', 1)[1].split(
        '<section id="settings-page" hidden>', 1
    )[0]
    assert '<button data-page="archive" hidden>찬양 자료실</button>' in html
    assert '<option value="archive" hidden>찬양 자료실</option>' in html
    assert '#archive-page{display:none!important}' in html
    assert '<details class="panel archive-history" id="archive-history" hidden>' in section
    # Preserve JS-mounted legacy elements until obsolete handlers can be retired safely.
    assert 'id="cloud-archive-refresh"' in section
    assert 'id="archive-library-manager"' in section
    assert 'id="cloud-archive-list"' in section


def test_archive_listing_stays_remote_and_selected_folder_survives_refresh():
    js = (UI / "onedrive.js").read_text(encoding="utf-8")
    archive_code = js.split(" async function archives(", 1)[1].split(
        " async function archiveCurrent(", 1
    )[0]
    assert "archiveView={purpose:chosen,id}" in archive_code
    assert "const items=(await api(query)).items;" in archive_code
    assert "const tab=button(label,()=>archives(key));" in archive_code
    assert "tab.setAttribute('aria-pressed',String(key===chosen));" in archive_code
    assert "const link=text('a','열기 ↗','cloud-download');" in archive_code
    assert "archives(archiveView.purpose,archiveView.id)" in js
    assert "if(el('archive-history').open)archives(archiveView.purpose,archiveView.id)" in js
    assert "api('import'" not in archive_code
    assert "api('download'" not in archive_code
