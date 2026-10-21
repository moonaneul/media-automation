"""The archive view is a remote OneDrive browser, not a local file import.

This checks visible interface copy without touching team files or credentials.
"""
from pathlib import Path


UI = Path("src/media_automation/web/original/ui")


def test_archive_browser_explains_source_in_heading_without_repeated_instructions():
    html = (UI / "index.html").read_text(encoding="utf-8")
    section = html.split('<section id="archive-page" hidden>', 1)[1].split(
        '<section id="settings-page" hidden>', 1
    )[0]
    assert "<h1>찬양 자료실</h1>" in section
    assert '<details class="panel archive-history" id="archive-history">' in section
    assert "과거 완료본 · 필요할 때만 열기" in section
    assert 'id="cloud-archive-refresh" type="button">새로고침</button>' in section
    assert section.index("<h2>등록된 찬양 원본</h2>") < section.index("과거 완료본 · 필요할 때만 열기")
    assert "<h2>등록된 찬양 원본</h2>" in section
    assert "OneDrive 보관 자료 새로고침" not in section
    assert "완료된 PPT·주보를 확인하고" not in section
    assert "주간 예배에 사용할 악보는 해당 찬양 항목에서 연결하세요" not in section


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
