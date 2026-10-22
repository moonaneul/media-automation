## 2026-10-22 운영 서비스 실행 정보 조회

- 실측 실행 계정: `media-web@church-media-511519.iam.gserviceaccount.com`.
- 설정된 **환경변수 이름만** 확인: `MEDIA_GCP_PROJECT`, `MEDIA_PUBLIC_ORIGIN`, `MEDIA_SUPABASE_PUBLISHABLE_KEY`, `MEDIA_SUPABASE_URL`, `MEDIA_WORKER_RESOURCE`. 직접 저장한 비밀키를 환경변수로 출력하지 않았다.
- 실제 운영 웹 이미지: `runtime-hosted@sha256:31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5` (변경 없음).
- 중요: 이미지의 `runtime_connection()`은 환경변수에 직접 표시되지 않는 **Secret Manager**의 `church-media-supabase`, `church-media-onedrive-key`를 읽는다. 환경변수 목록에 비밀이 없다는 사실로 새 서비스가 데이터에서 격리되었다고 판단할 수 없다.
- 다음 안전 단계는 기존 이미지의 프론트엔드 자산만 사용하여 **개별 IAM 비공개·무권한 서비스 계정·API 부재** 형태의 UI 미리보기 검증이다. 이 UI-only 서비스는 저장/제작/로그인을 테스트하지 않으며, 독립 Supabase/OneDrive 테스트 환경이 준비되기 전까지 통합 스테이징으로 부르지 않는다.


# 클라우드 통합 배포 전 읽기 전용 점검 (2026-10-22)

## 범위 및 현재 상태

- **검수 기준:** PR #15 (`fix/ui-workflow-20261015`), PR #14 (`cloud-runtime-20261014`) 위에 쌓인 통합 코드
- **기존 운영 환경 유지:** Mac 8876/로컬 DB, Windows 18878 테스트 DB, OneDrive 원본·완성본, Supabase 실제 입력
- **현재 클라우드가 최신 UI를 제공한다는 증거는 아직 없음.** 2026-10-14 배포·시험 기록은 그 당시 버전에만 해당한다.
- #15는 기존 자료실 화면을 숨기고 제작 화면의 찬양 원본 선택을 유지한다. 단지 로컬 UI가 정상이라는 이유로 클라우드 제작을 승인하지 않는다.
- 호스팅 웹은 `src/media_automation/cloud/server.py`에서 `web.original.server.make_server`를 사용하므로 빌드된 이미지 안의 `web/original/ui/index.html`이 UI 버전을 결정한다.

## 2026-10-22 Cloud Shell 실측 결과 (읽기 전용)

- 현재 웹 revision: `media-automation-00004-hrt`; Cloud Run 트래픽 100%.
- 웹과 제작 Job은 동일한 배포 이미지 `runtime-hosted@sha256:31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5` 사용.
- 제작 Job `Ready=True`, 웹 `/api/mode`는 허용된 아래 주소에서 HTTP 200이며 `hosted=true`, `shared=true`.
- 서버가 허용한 `MEDIA_PUBLIC_ORIGIN`: `https://media-automation-626807737784.asia-northeast3.run.app`. Cloud Run `status.url`에서 표시한 `https://media-automation-vdlt6fszqa-du.a.run.app`는 같은 서비스를 가리켜도 앱의 엄격한 Host 검사 때문에 HTTP 403.
- 외부 실제 HTML 메뉴는 `work`, `library`, `archive`, `settings` 네 개 모두 `hidden=False`로 검증됨. **현재 배포 이미지가 #15 최신 UI를 담고 있지 않음이 확인됐다.**
- `deploy/cloud/deploy-runtime.sh`를 그대로 실행하지 않는다. 이 스크립트는 `--no-allow-unauthenticated`를 적용하고 웹·Job을 곧바로 재배포하므로 이미 접속 가능한 공개 로그인 화면을 바꾸거나 사용자 트래픽에 영향을 줄 수 있다.
- 최신 UI 로컬·Windows 코드 테스트 통과 확인 → 기존 배포 및 리비전 복구 정보 보존 → 변경 없는 staging/무트래픽 리비전 검증 → 명시적 승인 후 트래픽 전환. 새 클라우드 작업 시작/기존 OneDrive 내용 수정 금지.

## Windows 집중 회귀 검증 결과 (사용자 실행: 2026-10-22)

- 검수 브랜치 `fix/ui-workflow-20261015`, 사용자 Windows checkout `50659b5`에서 실행.
- UI·찬양 연결·자료실 숨김·Cloud worker 보관 경로·다운로드 관련 다섯 파일: **17 passed in 0.81s**.
- 이전 6개 실패는 Windows 기본 CP949로 UTF-8 자료를 읽은 테스트 코드 문제였고, UTF-8 명시 수정 후 동일 테스트 재실행 통과.
- 이 결과는 **집중 회귀 테스트 통과**에 한정하며, 전체 테스트/클라우드 제작·업로드/실제 미디어 재생 성공을 증명하지 않는다.
- 다음 단계는 클라우드 경계/검수 승인/경합 처리 테스트 후 **별도 미리보기 호스트**로 검증하는 것. Cloud Run 태그별 별도 URL은 애플리케이션의 단일 `MEDIA_PUBLIC_ORIGIN` 검사에 걸릴 수 있으므로 태그만 붙여 접속 가능하다고 가정하지 않는다. 기존 `deploy-runtime.sh`는 즉시 운영 변경 위험이 있으므로 사용하지 않는다.

## Windows 검수 완료 API 회귀 검증 추가 기록 (2026-10-22)

- 클라우드 분류/목록/동시 작업/검수 승인 4파일 테스트: **48 passed, 7 failed** (Windows Python 3.13, 사용자 로그).
- 실패 7건 중 1건은 HTML 소스 `read_text()` CP949 해석 실패.
- 나머지 6건은 성공을 기대한 검수 완료 요청이 HTTP 400을 반환. 해당 테스트가 미디어 검수 JSON 보고서를 인코딩 지정 없이 `write_text`로 작성했고, 서버는 보고서를 `encoding='utf-8'`로 읽는다. Windows에서 CP949 바이트가 저장될 수 있어 승인 검증 전에 오류가 발생한 것으로 분석됨. 실제 400 응답 본문을 별도로 수집한 것은 아니므로 수정 후 회귀 결과를 반드시 확인한다.
- 수정: `tests/test_reviewed_worship_completion.py`에서 보고서 작성 및 HTML 읽기를 UTF-8로 명시, 모의 보고서 UTF-8 라운드트립 검사를 추가하여 검증 전 실패로 잘못된 음성 테스트 통과 방지. **서버 검수 조건은 완화하지 않았다.**
- **사용자 Windows 재실행 결과: 55 passed in 8.18s.** 승인·차단 분기 테스트가 함께 통과했으므로 해당 집중 회귀 차단 항목은 해소. 전체 회귀/클라우드 실배포 검증은 계속 남음.

## 1. GitHub 최신 코드 테스트 (Windows PowerShell)

Windows의 **검수용 폴더**에서 실행. 기존 `media-automation` 폴더, `main`, DB에는 아무것도 덮어쓰지 않는다.

```powershell
Set-Location "$HOME\Documents\media-automation-ui-review"
git status --short
git branch --show-current
```

`git status --short`가 비어 있고 브랜치가 `fix/ui-workflow-20261015`일 때만:

```powershell
git pull --ff-only origin fix/ui-workflow-20261015
.\.venv\Scripts\python.exe -m pytest -q tests/test_one_drive_lookup_ui.py tests/test_production_first_ui.py tests/test_archive_browser_minimal_ui.py tests/test_cloud_worker_archive_paths.py tests/test_download_feedback.py
```

- 실패 시 전체 파일을 재설치·초기화·`git reset --hard` 하지 않는다.
- 위 테스트는 코드 회귀 확인이며 Supabase/OneDrive 접속이나 금요 영상 실제 재생 성공을 증명하지 않는다.

## 2. Cloud Run 현재 상태 조회 (Google Cloud Shell)

**조회만** 실행한다. `gcloud run deploy`, `gcloud run jobs execute`, `gcloud run services update-traffic`는 실행하지 않는다. 셸에 로그인한 Google 계정에 조회 권한이 필요하다.

```bash
gcloud run services describe media-automation \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='json(status.url,status.latestReadyRevisionName,status.traffic)'
gcloud run services describe media-automation \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='value(spec.template.spec.containers[0].image)'

gcloud run jobs describe media-production \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='json(metadata.name,status.conditions)'
gcloud run jobs describe media-production \
  --project=church-media-511519 --region=asia-northeast3 \
  --format='value(spec.template.spec.template.spec.containers[0].image)'
```

출력에서 **서비스 주소, 현재 Ready revision, 실제 트래픽 대상 revision, 웹·Job 이미지**가 일치하는지 확인한다. 웹과 Job이 서로 다른 코드/이미지로 되어 있다면 배포 전 중단한다.

> 위 명령은 환경변수 목록을 출력하지 않도록 필요한 필드만 요청한다. 그래도 공유 전에 토큰·OAuth 비밀·이메일·파일 ID 등 민감 정보가 없는지 확인한다.

## 3. 외부 웹 읽기 전용 확인

클라우드 서비스 URL의 `/api/mode`에 비로그인 GET으로 접속한다. 기대값: `hosted: true`, `shared: true`, `local_only: false`. 보호된 API는 미인증 401이어야 한다. 접근 불가·타임아웃은 **미검증**으로 기록하고 서버 설정을 임의 변경하지 않는다.

Cloud Run에 새 이미지가 배포됐다고 해도 Supabase 팀원 로그인 → 데이터 조회·수정 충돌 처리 → PPT/PDF 제작 → 다운로드 → 완료본 OneDrive 보관 재검증은 별도로 필요하다.

## 4. 출시 차단 항목

1. 최신 UI/제작 코드의 전체 회귀 테스트 및 이미지 식별 확인
2. 검수 완료 → 미디어팀 지정 OneDrive 폴더의 파일 존재 및 재다운로드 확인
3. 금요 Zoom MP4/MP3 내장 및 Windows PowerPoint 실제 재생 확인
4. Mac-off + Windows에서 동일 Supabase 입력을 불러오고 제작·다운로드하는지 확인
5. Mac 로컬 입력/검수 기록과 Supabase가 달라지지 않았는지 읽기 전용 비교 후 승인된 전환

**현 단계에서는 기존 Mac 8876과 원본/DB를 보존하고 PR #14/#15를 병합하거나 운영 서비스를 갱신하지 않는다.**

## 2026-10-22 최신 이미지 빌드 실측 기록

- Cloud Build ID: `bda11545-5c01-4436-8304-196e4b194262`; **STATUS SUCCESS**; 빌드 37초.
- 빌드 소스 Git SHA: `1013c00fcfb435303f1712be29e71245be0b6e3e`; 최소화 컨텍스트 `1.7M`. 이후의 문서 기록 커밋과 이미지 원본 SHA는 구별한다.
- 이미지 태그: `asia-northeast3-docker.pkg.dev/church-media-511519/church-media/runtime-hosted:review-1013c00fcfb4`
- **고정 digest:** `asia-northeast3-docker.pkg.dev/church-media-511519/church-media/runtime-hosted@sha256:ac748f5854e2dfabb7f3f4c0cae13d9966991f32d46d797e4735b95cbe2b2e74`
- 기존 운영 이미지 digest `31b6839e918a8e75636d19bd86376a4515614f4a0d3a4e91e92bf3b029fe3be5`와 다름. Artifact Registry 업로드 성공일 뿐, 운영 Cloud Run 및 worker 배포는 아직 하지 않았다.
- 다음 검사: Cloud Shell에서 이미지 digest 조회 후 로컬 Docker `--network none`로 패키지 내 HTML 탐색·서버/worker 모듈 import; 비밀정보, 운영 Supabase 및 OneDrive 접속 없음. Google Cloud 프로젝트의 리소스·권한·트래픽 변경 없이 실행한다.

## 2026-10-22 이미지 내부 점검 (사용자 Cloud Shell 실행)

- `gcloud artifacts docker images describe`에서 고정 digest `sha256:ac748f5854e2dfabb7f3f4c0cae13d9966991f32d46d797e4735b95cbe2b2e74` 등록 확인.
- 해당 이미지를 `docker run --rm --network none`으로 실행했고 `media_automation.cloud.server`, `media_automation.cloud.worker` 모듈 import 성공.
- 설치된 `ui/index.html`에 대해 6개 확인 전부 PASS: 제작 메뉴, 자료실 메뉴 숨김, 자료실 화면 숨김, 검색 UI 유지, 원본 목록 유지, 설정 메뉴 유지.
- 위 검사에는 운영 접속·Supabase 로그인·PPT/PDF 생성·OneDrive 업로드가 포함되지 않는다. 기존 웹·제작 Job의 새 이미지 배포는 아직 하지 않았다.
- **스테이징 격리 제약:** 클라우드 웹 서버는 시작 시 `runtime_connection()`을 호출하고 기존 프로젝트의 `church-media-supabase` 및 `church-media-onedrive-key` Secret Manager 항목을 읽어 생산용 Supabase/OneDrive 클라이언트를 구성한다. 같은 이미지를 같은 프로젝트에 새 서비스 이름만 바꾸어 배포하고 운영 비밀 접근 권한을 주면 **격리된 스테이징이 아니다.** 프로덕션 권한을 복제해서 배포하면 안 된다. 별도 계정/백엔드를 격리하거나, 자격증명 불필요한 UI-only 미리보기임을 명시해 제한적인 화면 검수만 해야 한다.

## 5. 소스 최소화 이미지 빌드 (운영 배포 전, Cloud Shell)

> 승인된 별도 빌드 실행에만 사용. **Cloud Build와 Artifact Registry는 사용량에 따라 비용이 발생할 수 있다.** 빌드가 끝나도 Cloud Run 웹/Job 리비전과 트래픽은 변경하지 않는다.

아래는 전체 로컬 폴더·`output/`·`sources/`·DB·토큰을 클라우드에 보내지 않는다. GitHub의 추적된 `pyproject.toml`, `src/`, `deploy/cloud/Dockerfile.runtime`만 최소 빌드 컨텍스트로 만든다. 새 임시 폴더를 사용해 기존 체크아웃을 수정하지 않는다.

```bash
set -euo pipefail
BUILD_ROOT="$(mktemp -d)"
mkdir -p "$BUILD_ROOT/context"
GIT_LFS_SKIP_SMUDGE=1 git clone --depth 1 --single-branch \
  --branch fix/ui-workflow-20261015 \
  https://github.com/moonaneul/media-automation.git "$BUILD_ROOT/repo"
git -C "$BUILD_ROOT/repo" archive HEAD \
  pyproject.toml src deploy/cloud/Dockerfile.runtime | \
  tar -xf - -C "$BUILD_ROOT/context"
cp "$BUILD_ROOT/context/deploy/cloud/Dockerfile.runtime" "$BUILD_ROOT/context/Dockerfile"
SOURCE_SHA="$(git -C "$BUILD_ROOT/repo" rev-parse HEAD)"
IMAGE_TAG="asia-northeast3-docker.pkg.dev/church-media-511519/church-media/runtime-hosted:review-${SOURCE_SHA:0:12}"
printf 'Source SHA: %s\nBuild context: %s\nImage tag: %s\n' "$SOURCE_SHA" "$BUILD_ROOT/context" "$IMAGE_TAG"
du -sh "$BUILD_ROOT/context"
```

컨텍스트 목록·커밋·이미지 태그가 올바른지 확인한 뒤에만 다음 빌드를 실행한다.

```bash
gcloud builds submit "$BUILD_ROOT/context" \
  --project=church-media-511519 --region=asia-northeast3 \
  --tag "$IMAGE_TAG"
```

성공하면 이미지 digest로 고정하여 검수한다. **그 뒤에도 `deploy/cloud/deploy-runtime.sh`는 실행하지 않는다.** 특히 태그별 검수 URL은 앱의 단일 `MEDIA_PUBLIC_ORIGIN` 검사 때문에 403이 날 수 있으므로 안전하게 검수할 별도 호스트와 검수 DB/권한을 준비하기 전까지 실제 사용자 트래픽을 변경하지 않는다.

