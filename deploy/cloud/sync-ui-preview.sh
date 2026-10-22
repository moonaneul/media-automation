#!/usr/bin/env bash
# One-command, preview-only Cloud Run refresh until narrow GitHub OIDC is enabled.
# Run from a freshly cloned fix/ui-workflow-20261015 checkout in Cloud Shell.
set -euo pipefail

project='church-media-511519'
region='asia-northeast3'
service='media-ui-preview-1022'
preview_identity="media-ui-preview-1022@${project}.iam.gserviceaccount.com"
repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"
branch="$(git branch --show-current)"
if [[ "$branch" != "fix/ui-workflow-20261015" ]]; then
  echo 'This script only runs from the review UI branch.' >&2
  exit 1
fi

# Abort BEFORE build if the existing service is no longer an isolated private preview.
service_json="$(gcloud run services describe "$service" --project="$project" --region="$region" --format=json)"
SERVICE_JSON="$service_json" EXPECTED_IDENTITY="$preview_identity" python3 - <<'PY'
import json, os
d=json.loads(os.environ["SERVICE_JSON"])
spec=d["spec"]["template"]["spec"]
assert spec.get("serviceAccountName")==os.environ["EXPECTED_IDENTITY"], "Unexpected preview service account"
containers=spec["containers"]
assert len(containers)==1 and not containers[0].get("env"), "Preview must have no production env or secrets"
print("Private preview identity and empty environment confirmed")
PY
gcloud run services get-iam-policy "$service" --project="$project" --region="$region" --format=json |
  python3 -c 'import json,sys; p=json.load(sys.stdin); assert not any(m in ("allUsers","allAuthenticatedUsers") for b in p.get("bindings",[]) for m in b.get("members",[])), "Preview must remain private"'

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/context"
git archive HEAD src/media_automation/web/original/ui deploy/cloud/Dockerfile.ui-preview |
  tar -xf - -C "$tmp/context"
cp "$tmp/context/deploy/cloud/Dockerfile.ui-preview" "$tmp/context/Dockerfile"
commit="$(git rev-parse HEAD)"
image_tag="asia-northeast3-docker.pkg.dev/$project/church-media/media-ui-preview:branch-${commit:0:12}"
echo "Review source: $commit"
echo "Image: $image_tag"
gcloud builds submit "$tmp/context" --project="$project" --region="$region" --tag="$image_tag"
image_digest="$(gcloud artifacts docker images describe "$image_tag" --format='value(image_summary.fully_qualified_digest)')"
if [[ "$image_digest" != asia-northeast3-docker.pkg.dev/church-media-511519/church-media/media-ui-preview@sha256:* ]]; then
  echo 'Unexpected image digest: refusing deployment' >&2
  exit 1
fi

# Changes ONLY the separate static preview service, never the worship production service/job.
gcloud run services update "$service" --project="$project" --region="$region" \
  --image="$image_digest" \
  --command=python \
  --args="-m,http.server,8080,--bind,0.0.0.0,--directory,/srv/ui"

gcloud run services describe "$service" --project="$project" --region="$region" \
  --format='value(status.latestReadyRevisionName)'
echo 'Private UI-only preview refreshed. The production service and worker were not deployed.'
