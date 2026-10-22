#!/usr/bin/env python3
"""Read-only deployment inventory. Never deploy, read secrets, or infer approval.

Usage:
  python deploy/cloud/read_only_release_gate.py --live
  python deploy/cloud/read_only_release_gate.py --fixture-dir /path/to/json
"""
import argparse
import json
import subprocess
from pathlib import Path

PROJECT = "church-media-511519"
REGION = "asia-northeast3"
BASELINE = (
    "asia-northeast3-docker.pkg.dev/church-media-511519/church-media/"
    "runtime-hosted@sha256:31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5"
)
PREVIEW_IDENTITY = "media-ui-preview-1022@church-media-511519.iam.gserviceaccount.com"


def _containers(value):
    """Read containers from Cloud Run v1 resource formats; no arbitrary values printed."""
    if isinstance(value, dict):
        items = value.get("containers")
        if isinstance(items, list):
            return items
        for child in value.values():
            found = _containers(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _containers(child)
            if found is not None:
                return found
    return None


def _identity(resource):
    return resource.get("spec", {}).get("template", {}).get("spec", {}).get("serviceAccountName")


def _image(resource):
    containers = _containers(resource.get("spec", resource))
    if not containers or len(containers) != 1 or not isinstance(containers[0], dict):
        return ""
    return containers[0].get("image", "")


def _preview_env_empty(resource):
    containers = _containers(resource.get("spec", resource))
    return (
        isinstance(containers, list)
        and len(containers) == 1
        and not containers[0].get("env")
    )


def inventory(web, job, preview):
    """Fail closed: this only reports what is present, not approval to deploy."""
    web_image = _image(web)
    job_image = _image(job)
    preview_image = _image(preview)
    web_unchanged = web_image == BASELINE
    job_unchanged = job_image == BASELINE
    preview_isolated = (
        _identity(preview) == PREVIEW_IDENTITY and _preview_env_empty(preview)
        and bool(preview_image)
        and "/media-ui-preview/media-ui-preview@" in preview_image
    )
    return {
        "production_web": {
            "revision": web.get("status", {}).get("latestReadyRevisionName"),
            "image_digest": web_image,
            "unchanged_from_2026_10_22_baseline": web_unchanged,
        },
        "production_worker": {
            "image_digest": job_image,
            "unchanged_from_2026_10_22_baseline": job_unchanged,
        },
        "preview": {
            "revision": preview.get("status", {}).get("latestReadyRevisionName"),
            "image_digest": preview_image,
            "dedicated_runtime_identity": _identity(preview) == PREVIEW_IDENTITY,
            "environment_variables_absent": _preview_env_empty(preview),
            "isolated_ui_only_image": preview_isolated,
        },
        "unexpected_operational_change": not (web_unchanged and job_unchanged and preview_isolated),
        "live_supabase_and_onedrive_integration_verified": False,
        "manual_visual_review_verified": False,
        "authorized_for_production_deployment": False,
    }


def read_live(resource, name):
    if resource not in ("services", "jobs"):
        raise ValueError("Unsupported read-only resource")
    if name not in ("media-automation", "media-production", "media-ui-preview-1022"):
        raise ValueError("Unexpected resource name")
    output = subprocess.check_output(
        ["gcloud", "run", resource, "describe", name,
         "--project=" + PROJECT, "--region=" + REGION, "--format=json"],
        text=True, timeout=30,
    )
    return json.loads(output)


def main():
    parser = argparse.ArgumentParser()
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--live", action="store_true")
    target.add_argument("--fixture-dir", type=Path)
    args = parser.parse_args()

    if args.live:
        web = read_live("services", "media-automation")
        job = read_live("jobs", "media-production")
        preview = read_live("services", "media-ui-preview-1022")
    else:
        folder = args.fixture_dir
        web = json.loads((folder / "web.json").read_text(encoding="utf-8"))
        job = json.loads((folder / "job.json").read_text(encoding="utf-8"))
        preview = json.loads((folder / "preview.json").read_text(encoding="utf-8"))
    report = inventory(web, job, preview)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["unexpected_operational_change"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
