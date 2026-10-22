"""The Cloud Run UI preview must remain non-destructive and understandable."""
from pathlib import Path

UI = Path(__file__).resolve().parents[1] / "src/media_automation/web/original/ui"


def test_friday_format_is_a_two_choice_toggle_without_losing_mode_snapshots():
    html = (UI / "index.html").read_text(encoding="utf-8")
    section = html.split("function renderFridayMode(){", 1)[1].split(
        "\nfunction setFieldAbsent", 1
    )[0]
    assert "node('div',undefined,'friday-mode-toggle')" in section
    assert "['zoom','Zoom 비대면']" in section
    assert "['in_person','예배당 대면']" in section
    assert "button.type='button'" in section
    assert "button.setAttribute('aria-pressed',String(fridayMode()===value))" in section
    assert "select.id='friday-mode'" in section
    assert "select.hidden=true" in section
    assert "select.value=value;select.onchange()" in section
    assert "r.fridayModeStates[old]=snapshot" in section
    assert "r.fridayMode=select.value;save();render()" in section
    assert '.friday-mode-toggle>.friday-mode-option:focus-visible' in html


def test_preview_one_drive_errors_never_expose_raw_html_json_exception():
    js = (UI / "onedrive.js").read_text(encoding="utf-8")
    api = js.split(" async function api(", 1)[1].split(
        "\n function button(", 1
    )[0]
    assert "r.headers.get('content-type')" in api
    assert "if(!contentType.includes('json'))" in api
    assert "디자인 미리보기에서는 OneDrive 연결과 저장을 사용할 수 없습니다." in api
    assert "try{data=await r.json();}" in api
    assert "if(!r.ok)throw Error(data?.error||" in api


def test_preview_dockerfile_static_only_and_no_cloud_server_startup():
    docker = (UI.parents[4] / "deploy/cloud/Dockerfile.ui-preview").read_text(
        encoding="utf-8"
    )
    assert "COPY src/media_automation/web/original/ui ./ui" in docker
    assert 'USER 10001' in docker
    assert 'ENTRYPOINT ["python", "-m", "http.server"' in docker
    assert "media_automation.cloud.server" not in docker
    assert "COPY src ./src" not in docker
