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
- 배포 차단: 수정 후 동일 4개 파일 Windows 재실행에서 성공·차단 사례 모두 통과하는지 확인할 것.

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
