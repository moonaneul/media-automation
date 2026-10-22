# GitHub Actions → 비공개 UI 미리보기만 배포 (2026-10-22)

## 실제 확인된 초기 상태

- `church-ui-preview` Workload Identity Pool 생성됨.
- `github-ui-preview` OIDC Provider `ACTIVE`. 리소스: `projects/626807737784/locations/global/workloadIdentityPools/church-ui-preview/providers/github-ui-preview`.
- Provider의 조건은 GitHub 저장소 불변 ID `1394499062`, 소유자 ID `109272284`, 브랜치 `refs/heads/fix/ui-workflow-20261015`, `.github/workflows/ui-preview-sync.yml`, push/workflow_dispatch를 제한한다.
- 아직 서비스 계정 위임과 Cloud Run 권한 부여 및 GitHub variables 설정은 별도 확인 필요.

## 최소 권한 구성

중요: **프로젝트 전체** `roles/run.admin`, `roles/run.developer`, `roles/cloudbuild.builds.editor`, Secret Manager Reader, `roles/owner`를 배포 계정에 부여하지 않는다. 별도의 `media-ui-preview` Artifact Registry repository만 쓰고 GitHub의 Docker runner에서 이미지를 빌드한다. 공식 `python:3.12-slim-bookworm`를 기본 이미지로 이용하여 기존 `church-media` 생산 이미지 저장소 읽기 권한조차 필요 없다.

Google Cloud Shell에서 실행할 단계:

```bash
PROJECT=church-media-511519
REGION=asia-northeast3
NUMBER=626807737784
DEPLOYER=media-preview-deployer@${PROJECT}.iam.gserviceaccount.com
RUNTIME=media-ui-preview-1022@${PROJECT}.iam.gserviceaccount.com

gcloud iam service-accounts create media-preview-deployer \
  --project="$PROJECT" --display-name="Restricted preview deployer"
gcloud artifacts repositories create media-ui-preview \
  --project="$PROJECT" --location="$REGION" --repository-format=docker \
  --description="Only non-production static UI preview images"

# Trust only the already condition-limited GitHub provider, then allow identity impersonation.
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER" \
  --project="$PROJECT" --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/$NUMBER/locations/global/workloadIdentityPools/church-ui-preview/attribute.repo_id/1394499062"

# Image write/read is restricted to the new UI-only repository.
gcloud artifacts repositories add-iam-policy-binding media-ui-preview \
  --project="$PROJECT" --location="$REGION" \
  --member="serviceAccount:$DEPLOYER" --role=roles/artifactregistry.writer

# Cloud Run developer has update/delete capabilities, but ONLY on this preview service.
gcloud run services add-iam-policy-binding media-ui-preview-1022 \
  --project="$PROJECT" --region="$REGION" \
  --member="serviceAccount:$DEPLOYER" --role=roles/run.developer

# actAs can be used ONLY with the no-secrets preview runtime account.
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME" \
  --project="$PROJECT" \
  --member="serviceAccount:$DEPLOYER" --role=roles/iam.serviceAccountUser
```

여기서 사용한 서비스 계정/아티팩트 저장소는 새로 생성되는 별도 자원이며 프로젝트 요금에 영향을 줄 수 있다. 이미 생성되어 있다는 오류가 발생하면 그대로 실행을 반복하지 말고 실제 상태를 조회한다.

## Cloud Shell 실제 설정 결과 (2026-10-22)

- `media-preview-deployer@church-media-511519.iam.gserviceaccount.com` 생성 성공.
- `media-ui-preview` Docker Artifact Registry 별도 저장소 생성 성공.
- `roles/iam.workloadIdentityUser`는 GitHub 저장소 ID 1394499062의 WIF principalSet에 배포 계정 단위로 부여됨.
- `roles/artifactregistry.writer`는 **새 `media-ui-preview` 저장소에만** 부여됨.
- `roles/run.developer`는 **`media-ui-preview-1022` 서비스에만** 부여됨.
- `roles/iam.serviceAccountUser`는 **`media-ui-preview-1022` 실행 계정에만** 부여됨.
- 위 4개 IAM 정책 업데이트는 사용자가 Cloud Shell 출력으로 완료 확인. 운영 서비스/제작 Job IAM 변경을 실행한 기록은 없음.
- 남은 단계: GitHub 저장소의 repository Actions Variables 2개 등록, 배포 Job 실실행 로그 검증. 첫 GitHub 자동 배포 실패 시 무작정 권한 확대하지 말고 필요한 특정 권한만 조사한다.

## GitHub Actions repository Variables

GitHub 저장소 `moonaneul/media-automation` → **Settings → Secrets and variables → Actions → Variables → New repository variable**에서 다음 이름/값을 등록한다. 공개 가능한 GCP 리소스 이름들이지만 이 값 자체는 비밀번호가 아니다.

- `MEDIA_PREVIEW_WIF_PROVIDER` = `projects/626807737784/locations/global/workloadIdentityPools/church-ui-preview/providers/github-ui-preview`
- `MEDIA_PREVIEW_DEPLOYER_SA` = `media-preview-deployer@church-media-511519.iam.gserviceaccount.com`

둘 모두 설정되어야 `.github/workflows/ui-preview-sync.yml`에서 `deploy-ui-preview` Job을 실행하도록 조건을 걸어 두었다.

기존 운영 이미지/웹 서비스/Job, 실제 Supabase/OneDrive는 배포 계정 권한 범위에서 제외한다. 미리보기 서비스는 정적 HTTP 파일만 제공하며, 시작 시 Cloud Secret Manager를 호출하지 않는다.

## 사후 검수

```bash
gcloud run services describe media-ui-preview-1022 \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
gcloud run services describe media-automation \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='value(status.latestReadyRevisionName,spec.template.spec.containers[0].image)'
gcloud run jobs describe media-production \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='value(spec.template.spec.template.spec.containers[0].image)'
```

프리뷰 리비전만 바뀌어야 한다. 새로운 GitHub Actions 체크가 통과했고 별도 미리보기 UI를 육안 확인하기 전까지 운영 반영하지 않는다. 비밀번호, 클라이언트 비밀키, 서비스 계정 JSON 파일은 출력하거나 GitHub에 커밋하지 않는다.

## GitHub Actions 첫 자동 배포 성공 (2026-10-22)

- 사용자가 GitHub Actions repository variables `MEDIA_PREVIEW_WIF_PROVIDER`와 `MEDIA_PREVIEW_DEPLOYER_SA` 등록 완료를 통보.
- 검수 브랜치 커밋 `6d3c8432f448dae7487eab98c250d681953ff516` (`ui-preview-sync.yml`의 `node --check` 추가)이 GitHub `push` 이벤트를 트리거했다.
- GitHub Actions [Safe UI Preview Sync 실행 #8](https://github.com/moonaneul/media-automation/actions/runs/39715624076): `Test preview-only UI` **success**, `Update ONLY private media-ui-preview-1022` **success**.
- 배포 Job 내 Workload Identity OIDC 인증 성공, 비공개 미리보기 계정·빈 환경변수 검사 성공, 별도 Artifact Registry 저장소로 Docker build/push 성공.
- 새 이미지 `asia-northeast3-docker.pkg.dev/church-media-511519/media-ui-preview/media-ui-preview@sha256:4f3e2c4a07c92eae9e71a75bda881de1402fdcdd7fa6cebb56e483486345eccb`.
- GitHub Action 로그에서 리비전 `media-ui-preview-1022-00003-rst` 배포 `Done`, **미리보기 서비스 트래픽 100%**가 확인됨.
- 운영 웹 `media-automation`/Job `media-production` 배포 단계 없음; 배포 주체 IAM은 별도 UI 미리보기 서비스·이미지 저장소·실행 계정 범위에 국한된다. 이는 운영환경 전체의 사후 실측 확인을 대체하지 않는다.
- 사용자 브라우저 UI 시각 검증 및 실제 원본/예배 제작·OneDrive 연동 검증은 별개이며 아직 실시하지 않았다.
