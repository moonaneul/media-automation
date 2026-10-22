# 클라우드 통합 배포 전 읽기 전용 점검 (2026-10-22)

## 범위 및 현재 상태

- **검수 기준:** PR #15 (`fix/ui-workflow-20261015`), PR #14 (`cloud-runtime-20261014`) 위에 쌓인 통합 코드
- **기존 운영 환경 유지:** Mac 8876/로컬 DB, Windows 18878 테스트 DB, OneDrive 원본·완성본, Supabase 실제 입력
- **현재 클라우드가 최신 UI를 제공한다는 증거는 아직 없음.** 2026-10-14 배포·시험 기록은 그 당시 버전에만 해당한다.
- #15는 기존 자료실 화면을 숨기고 제작 화면의 찬양 원본 선택을 유지한다. 단지 로컬 UI가 정상이라는 이유로 클라우드 제작을 승인하지 않는다.
- 호스팅 웹은 `src/media_automation/cloud/server.py`에서 `web.original.server.make_server`를 사용하므로 빌드된 이미지 안의 `web/original/ui/index.html`이 UI 버전을 결정한다.

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
