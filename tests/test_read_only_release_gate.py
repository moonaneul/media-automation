"""Read-only release inventory must fail closed without needing real GCP credentials."""
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/cloud/read_only_release_gate.py"
spec = importlib.util.spec_from_file_location("media_release_inventory_readonly", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def fixture_resources(*, baseline=True, preview_clean=True):
    web = {
        "spec": {"template": {"spec": {
            "serviceAccountName": "media-web@church-media-511519.iam.gserviceaccount.com",
            "containers": [{"image": gate.BASELINE}]
        }}},
        "status": {"latestReadyRevisionName": "production-kept"}
    }
    worker = {
        "spec": {"template": {"spec": {"template": {"spec": {
            "containers": [{"image": gate.BASELINE}]
        }}}}}
    }
    preview = {
        "spec": {"template": {"spec": {
            "serviceAccountName": gate.PREVIEW_IDENTITY,
            "containers": [{"image":
                "asia-northeast3-docker.pkg.dev/church-media-511519/media-ui-preview/"
                "media-ui-preview@sha256:" + "a" * 64}]
        }}},
        "status": {"latestReadyRevisionName": "isolated-preview"}
    }
    if not baseline:
        worker["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]["image"] = (
            "unexpected-operational-image"
        )
    if not preview_clean:
        preview["spec"]["template"]["spec"]["containers"][0]["env"] = [
            {"name": "SENSITIVE_CONNECTION_VARIABLE", "value": "must-not-print"}
        ]
    return web, worker, preview


def test_clean_inventory_is_still_not_production_approval():
    report = gate.inventory(*fixture_resources())
    assert report["unexpected_operational_change"] is False
    assert report["preview"]["isolated_ui_only_image"] is True
    assert report["production_web"]["unchanged_from_2026_10_22_baseline"] is True
    assert report["production_worker"]["unchanged_from_2026_10_22_baseline"] is True
    assert report["authorized_for_production_deployment"] is False
    assert report["live_supabase_and_onedrive_integration_verified"] is False


@pytest.mark.parametrize("reason", ["image", "environment", "identity", "repository"])
def test_any_unexpected_change_blocks_readonly_gate(reason):
    web, job, preview = fixture_resources()
    if reason == "image":
        web["spec"]["template"]["spec"]["containers"][0]["image"] = "unexpected"
    elif reason == "environment":
        preview["spec"]["template"]["spec"]["containers"][0]["env"] = [
            {"name": "SECRET_VALUE", "value": "do-not-print"}
        ]
    elif reason == "identity":
        preview["spec"]["template"]["spec"]["serviceAccountName"] = (
            "media-web@church-media-511519.iam.gserviceaccount.com"
        )
    else:
        preview["spec"]["template"]["spec"]["containers"][0]["image"] = gate.BASELINE
    report = gate.inventory(web, job, preview)
    assert report["unexpected_operational_change"] is True
    assert report["authorized_for_production_deployment"] is False
    assert "do-not-print" not in json.dumps(report)


def test_command_line_checks_only_synthetic_json_and_never_emits_env_values(tmp_path):
    web, worker, preview = fixture_resources(preview_clean=False)
    for key, obj in (("web", web), ("job", worker), ("preview", preview)):
        (tmp_path / (key + ".json")).write_text(json.dumps(obj), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--fixture-dir", str(tmp_path)],
        capture_output=True, text=True, check=False
    )
    assert completed.returncode == 2
    body = json.loads(completed.stdout)
    assert body["unexpected_operational_change"] is True
    assert body["authorized_for_production_deployment"] is False
    assert "must-not-print" not in completed.stdout
    assert "SENSITIVE_CONNECTION_VARIABLE" not in completed.stdout


def test_production_gate_contains_no_write_operations():
    source = SCRIPT.read_text(encoding="utf-8")
    assert '"gcloud", "run", resource, "describe"' in source
    assert "gcloud run deploy" not in source
    assert "gcloud run services update" not in source
    assert "gcloud run jobs update" not in source
    assert "load_secret(" not in source
    assert "def read_live(" in source
