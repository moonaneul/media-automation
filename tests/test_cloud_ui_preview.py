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
    assert "r.headers?.get?.('content-type')" in api
    assert "if(contentType && !contentType.includes('json'))" in api
    assert "디자인 미리보기에서는 OneDrive 연결과 저장을 사용할 수 없습니다." in api
    assert "try{data=await r.json();}" in api
    assert "if(!r.ok)throw Error(data?.error||" in api


def test_preview_dockerfile_static_only_and_no_cloud_server_startup():
    docker = (UI.parents[4] / "deploy/cloud/Dockerfile.ui-preview").read_text(
        encoding="utf-8"
    )
    assert "FROM python:3.12-slim-bookworm" in docker
    assert "COPY src/media_automation/web/original/ui ./ui" in docker
    assert 'USER 10001' in docker
    assert 'ENTRYPOINT ["python", "-m", "http.server"' in docker
    assert "media_automation.cloud.server" not in docker
    assert "COPY src ./src" not in docker


def test_preview_sync_remains_private_and_never_touches_production():
    root = UI.parents[4]
    workflow = (root / ".github/workflows/ui-preview-sync.yml").read_text(
        encoding="utf-8"
    )
    script = (root / "deploy/cloud/sync-ui-preview.sh").read_text(
        encoding="utf-8"
    )
    for text in (workflow, script):
        assert "media-ui-preview-1022" in text
        assert "media-automation --" not in text
        assert "media-production" not in text
        assert "--no-allow-unauthenticated" not in text
        assert "allAuthenticatedUsers" in text and "allUsers" in text
        assert "/media-ui-preview/media-ui-preview:branch-" in text
        assert "Dockerfile.ui-preview" in text
        assert "ui-preview-context" in text or 'git archive HEAD' in text
    assert "vars.MEDIA_PREVIEW_WIF_PROVIDER != ''" in workflow
    assert "vars.MEDIA_PREVIEW_DEPLOYER_SA != ''" in workflow
    assert "google-github-actions/auth@v2" in workflow
    assert "id-token: write" in workflow
    assert "git archive HEAD" in script
    assert "gcloud builds submit" not in workflow
    assert "docker build --pull" in workflow
    assert "docker push" in workflow
    assert "/church-media/media-ui-preview:" not in workflow
    assert "gcloud run deploy media-automation" not in workflow


def test_settings_cards_have_consistent_full_width_parent_and_notice_order():
    """The bulletin card should not occupy half a row above full-width storage."""
    from html.parser import HTMLParser

    source = (UI / "index.html").read_text(encoding="utf-8")
    fragment = source.split('<section id="settings-page" hidden>', 1)[1].split(
        "\n</section>", 1
    )[0]
    fragment = '<section id="settings-page" hidden>' + fragment + "\n</section>"

    class Inspect(HTMLParser):
        VOID = {"input", "br", "hr", "img", "meta", "link", "source", "area"}

        def __init__(self):
            super().__init__()
            self.stack = []
            self.parents = {}
            self.cloud_status_parent = None
            self.cloud_status_title_ancestor = False

        def handle_starttag(self, tag, attributes):
            attributes = dict(attributes)
            ident = attributes.get("id", "")
            if ident in ("bulletin-base-settings", "cloud-storage-settings", "team-access-settings"):
                assert tag == "div"
                self.parents[ident] = self.stack[-1][1].get("class")
            if ident == "cloud-status":
                self.cloud_status_parent = self.stack[-1][1].get("class")
                self.cloud_status_title_ancestor = any(
                    "settings-heading" in a.get("class", "")
                    for _, a in self.stack
                )
            if tag not in self.VOID:
                self.stack.append((tag, attributes))

        def handle_endtag(self, tag):
            assert self.stack, f"Unexpected closing {tag}"
            opened, _ = self.stack.pop()
            assert opened == tag, f"Unexpected </{tag}> after <{opened}>"

    inspect = Inspect()
    inspect.feed(fragment)
    assert not inspect.stack
    assert inspect.parents == {
        "bulletin-base-settings": "settings-grid",
        "cloud-storage-settings": "settings-grid",
        "team-access-settings": "settings-grid",
    }
    assert inspect.cloud_status_parent == "settings-notice-row"
    assert not inspect.cloud_status_title_ancestor
    assert "role=\"status\" aria-live=\"polite\"" in fragment
    assert "#settings-page .settings-grid{\n  display:grid;\n  grid-template-columns:minmax(0,1fr)" in source
    assert "#settings-page .settings-notice-row #cloud-status{\n  display:block;\n  width:100%" in source
    assert "@media(max-width:640px){\n  #settings-page .settings-grid{gap:16px}" in source
