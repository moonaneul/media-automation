#!/usr/bin/env bash
# Run only after reviewing IAM + SQL. No secrets are printed or new versions created.
set -euo pipefail
project=church-media-511519
region=asia-northeast3
web_account="media-web@${project}.iam.gserviceaccount.com"
worker_account="media-runtime@${project}.iam.gserviceaccount.com"
image="${1:?Supply the reviewed immutable image digest}"
if [[ ! "$image" =~ ^asia-northeast3-docker.pkg.dev/church-media-511519/church-media/runtime-hosted@sha256:[a-f0-9]{64}$ ]]; then
  echo 'Use the reviewed runtime-hosted image digest.' >&2
  exit 1
fi
origin='https://media-automation-626807737784.asia-northeast3.run.app'
worker_resource="projects/${project}/locations/${region}/jobs/media-production"
# This script deliberately requires a separate web identity, never project-wide run.admin.
gcloud iam service-accounts describe "$web_account" --project="$project" >/dev/null 2>&1 ||
  gcloud iam service-accounts create media-web --project="$project" --display-name='Church media web'
for secret in church-media-supabase church-media-onedrive-key; do
  gcloud secrets add-iam-policy-binding "$secret" --project="$project" \
    --member="serviceAccount:${web_account}" --role=roles/secretmanager.secretAccessor >/dev/null
done
# Existing worker retains its verified secret permissions. No bootstrap version-adder added.
gcloud run jobs deploy media-production --project="$project" --region="$region" \
  --image="$image" --service-account="$worker_account" --container=worker \
  --command=python --args=-m,media_automation.cloud.worker \
  --tasks=1 --parallelism=1 --max-retries=0 --task-timeout=840s --cpu=1 --memory=4Gi \
  --set-env-vars=MEDIA_GCP_PROJECT="$project",MEDIA_SUPABASE_URL=https://rzqvhldujuaeqnckxezw.supabase.co
# Resource-level execution permission only. The API accepts no user-selected command/image/env.
gcloud run jobs add-iam-policy-binding media-production --project="$project" --region="$region" \
  --member="serviceAccount:${web_account}" --role=roles/run.jobsExecutorWithOverrides >/dev/null
gcloud run deploy media-automation --project="$project" --region="$region" \
  --image="$image" --service-account="$web_account" --port=8080 \
  --min=0 --max=1 --concurrency=1 --timeout=300 --cpu=1 --memory=2Gi \
  --no-allow-unauthenticated \
  --set-env-vars=MEDIA_GCP_PROJECT="$project",MEDIA_SUPABASE_URL=https://rzqvhldujuaeqnckxezw.supabase.co,MEDIA_SUPABASE_PUBLISHABLE_KEY=sb_publishable_038LJ1Y5eNWnMkzrbR4Pwg_ogJOxxt5,MEDIA_PUBLIC_ORIGIN="$origin",MEDIA_WORKER_RESOURCE="$worker_resource"
echo 'Private web and production job deployed. Public access remains a separate reviewed step.'
gcloud run services describe media-automation --project="$project" --region="$region" --format='value(status.url)'
