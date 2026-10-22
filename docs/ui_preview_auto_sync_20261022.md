# UI 미리보기 자동 갱신 및 운영 보호 (2026-10-22)

## 목적

GitHub 검수 브랜치 `fix/ui-workflow-20261015`에서 UI를 수정하면 회귀 테스트를 자동 실행하고, **별도 비공개 Cloud Run 서비스 `media-ui-preview-1022`만** 갱신하도록 설계한다. 실제 예배 제작실 `media-automation`, 제작 Job `media-production`, 원본 OneDrive, Supabase 업무 데이터는 변경하지 않는다.

## 반영된 UI 수정

- 금요기도회 `fridayMode` 선택: Zoom 비대면/예배당 대면이 한눈에 보이는 두 버튼. 화면 내부의 선택 변경은 기존 `fridayModeStates`별 별도 기록 저장·복구를 그대로 호출한다.
- 정적 미리보기의 OneDrive API는 제공되지 않음. `/api/onedrive/*`에서 HTML/404를 받았을 때 원시 `Unexpected token '<'` 오류 대신 '디자인 미리보기에서는 OneDrive 연결과 저장을 사용할 수 없습니다'라고 보여 준다. 실운영의 JSON 오류 메시지와 인증/권한 검사는 기존대로 유지한다.
- 미리보기를 위한 `deploy/cloud/Dockerfile.ui-preview`는 `ui/` 정적 파일만 포함한다. 웹 서버는 읽기 전용 `python -m http.server`; Cloud 백엔드·미디어 제작 Job이 이미지에 포함되지 않는다.

## 자동화: 준비된 부분 / 실제로 남은 연결

- `.github/workflows/ui-preview-sync.yml`은 검수 브랜치의 UI 파일·미리보기 Dockerfile·관련 테스트가 바뀌면 자동 실행되며, 회귀 테스트 후 미리보기 소스 아티팩트를 남기도록 작성했다.
- **Google Cloud 자동 배포는 현재 연결 검증 전이다.** 배포 Job은 GitHub Actions repository variables `MEDIA_PREVIEW_WIF_PROVIDER`, `MEDIA_PREVIEW_DEPLOYER_SA`가 모두 설정된 경우에만 작동하게 제한했다. 두 변수가 없으면 자동 테스트/아티팩트 단계만 진행하고, 클라우드 배포는 건너뛴다.
- Workload Identity Federation을 사용할 때는 비밀 서비스 계정 키를 GitHub에 저장하지 않는다. GCP에서 **정확한 GitHub 저장소 + `fix/ui-workflow-20261015` 브랜치 + 해당 workflow만** 허용하도록 provider attribute condition을 제한한다.
- 배포용 서비스 계정은 미리보기 Cloud Run 서비스 업데이트, 해당 저장소에 미리보기 이미지 빌드/쓰기, `media-ui-preview-1022` 실행 계정 impersonation에 필요한 최소 역할만 승인한다. `roles/owner`, 프로젝트 전체 `roles/run.admin`, Secret Manager 읽기, 프로덕션 웹·Job 변경 권한은 부여하지 않는다. 실제 필요한 Cloud Build/Storage/Artifact Registry 권한은 설정 전 GCP에서 검토한다.
- 자동 배포 Job은 비공개 IAM 상태, 기존 미리보기용 실행 계정, **환경변수 없음**을 검사한 뒤 UI 파일만 골라 이미지로 만들고 `media-ui-preview-1022`만 업데이트한다. 조건 위반 시 중단한다.
- 소스 브랜치 PR 병합, 운영 트래픽 전환, 실제 예배자료 제작·보관은 자동화하지 않는다.

## OIDC 인증 연결 전, Cloud Shell 한 번에 미리보기 갱신하기

Windows가 아닌 Google Cloud Shell에서 실행. 새로운 임시 체크아웃을 생성하므로 기존 Mac·Windows 폴더에 영향을 주지 않는다.

```bash
PREVIEW_SOURCE="$(mktemp -d)"
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --single-branch \
  --branch fix/ui-workflow-20261015 \
  https://github.com/moonaneul/media-automation.git "$PREVIEW_SOURCE/repo"
cd "$PREVIEW_SOURCE/repo"
bash deploy/cloud/sync-ui-preview.sh
```

이 명령은 Artifact Registry에서 **새 정적 UI 이미지 빌드 및 비공개 미리보기 서비스만 재배포**하며 사용량에 따라 비용이 발생할 수 있다. 스크립트가 기존 미리보기 계정·공개 IAM 권한·빈 환경변수를 먼저 검증하므로 잘못된 서비스가 연결되어 있으면 실패한다. 원본 폴더·운영 서비스나 Job은 변경하지 않는다.

프록시 접속 (다른 Cloud Shell 세션 또는 별도 터미널):

```bash
gcloud run services proxy media-ui-preview-1022 \
  --project=church-media-511519 --region=asia-northeast3 --port=8080
```

Cloud Shell의 웹 미리보기에서 포트 8080을 확인한다. 로그인·제작·OneDrive API는 원래 없는 **디자인 확인용 서비스**이다.

## 검증 기준

1. 검수용 Windows 브랜치에서 `git pull --ff-only origin fix/ui-workflow-20261015` 후 `python -m pytest -q tests/test_cloud_ui_preview.py tests/test_one_drive_lookup_ui.py tests/test_production_first_ui.py tests/test_archive_browser_minimal_ui.py tests/test_download_feedback.py` 성공.
2. 미리보기 화면에서 금요 Zoom/예배당 대면이 두 버튼으로 표시, 키보드 선택 가능. 진행방식 변경 전에는 기존 주차의 대면/Zoom 입력을 유지한다.
3. OneDrive 부분이 원시 JSON 파싱 예외를 사용자에게 표시하지 않는다. '미리보기에서는 사용 불가' 안내가 보인다.
4. 운영 서비스 `media-automation`의 트래픽·이미지와 `media-production` Job 이미지는 변경 전과 동일한지 검증한다.
5. UI-only 미리보기 성공을 Supabase 동기화, 실제 PPT/PDF 생성·OneDrive 업로드의 통합 테스트 성공으로 판단하지 않는다.

## 현재 상태

- 코드/UI 개선과 테스트, 자동 테스트 + 선택적 OIDC 배포 워크플로 및 수동 갱신 스크립트를 **검수 브랜치에 저장**했다.
- 새 UI의 최신 Cloud Run 미리보기 재배포 및 Workload Identity 설정은 **아직 실제 완료 결과가 없다**.
- 운영 Cloud Run은 기존 `runtime-hosted@sha256:31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5`를 유지해야 한다.

## 추가 검수 기록 (2026-10-22)

- Windows 검수 체크아웃을 `c61b3cd`까지 fast-forward한 후 `tests/test_cloud_ui_preview.py`, `tests/test_one_drive_lookup_ui.py`, `tests/test_production_first_ui.py`, `tests/test_archive_browser_minimal_ui.py`, `tests/test_download_feedback.py`를 실행하여 **17 passed in 0.23s** 확인.
- 이는 클라우드 자동 배포나 운영 서비스 적용 성공을 뜻하지 않는다. Cloud Run 프리뷰 갱신과 실화면 검수는 별도로 수행해야 한다.

## Cloud Shell 미리보기 실제 배포 성공 기록 (2026-10-22)

- 실측 소스 커밋: `55c5e920ca48ff5626a093b3df2e49e90fdc0f4e`.
- `deploy/cloud/sync-ui-preview.sh` 실행 시 비공개 서비스 계정 및 빈 환경변수 검사 성공.
- 새 정적 UI 이미지: `asia-northeast3-docker.pkg.dev/church-media-511519/church-media/media-ui-preview@sha256:85067cc61065c3b7b10f1b79ffa126b64262f05f7ce06d02ba5812763092ccea`.
- Cloud Build `9f5f97fe-a4e3-4bd2-8ec3-78fe45398fa6` SUCCESS; Cloud Run **미리보기 서비스만** 리비전 `media-ui-preview-1022-00002-dh9`로 갱신 성공.
- 아직 브라우저 육안 검수/자동 OIDC 연결은 미확인. 기존 `media-automation` 웹 및 `media-production` 제작 Job 배포 명령은 실행하지 않았다.
