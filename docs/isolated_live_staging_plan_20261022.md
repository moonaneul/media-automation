# 실제 제작 통합 검수용 독립 스테이징 설계 (2026-10-22)

## 목적과 현재 상태

2026-10-22 Cloud Shell 읽기 전용 점검에서 실제 운영 웹/Job은 **원래 이미지** `sha256:31b6839e...`로 유지되는 것이 확인되었다. 비공개 UI 미리보기는 독립된 `media-ui-preview-1022`이며 **정적 파일만 제공**하므로 API·PPT·주보 생성은 검증하지 못한다.

별도 CI의 합성 데이터 테스트는 **85 passed**. 기존 운영 런타임을 사용한 **2026-10-14 당시의 실제 PPT/주보 생성 및 OneDrive 보관 시험 기록**은 [hosted_runtime_20261014.md](hosted_runtime_20261014.md)에 있으며, 이는 2026-10-22 **새 검수 브랜치의 End-to-End 검증 결과가 아니다**.

## 새 리소스가 필요한 이유

검수 브랜치의 서버 `src/media_automation/cloud/server.py`는 실행 시 `worker.runtime_connection()`을 호출한다. 이 함수는 기본 GCP 프로젝트를 `church-media-511519`로 잡고 다음 Secret Manager 값을 읽는다.

- `projects/<MEDIA_GCP_PROJECT>/secrets/church-media-supabase`
- `projects/<MEDIA_GCP_PROJECT>/secrets/church-media-onedrive-key` (version 1)

환경변수 `MEDIA_SUPABASE_URL`, `MEDIA_SUPABASE_PUBLISHABLE_KEY`, `MEDIA_WORKER_RESOURCE`, `MEDIA_PUBLIC_ORIGIN` 역시 사용한다. SQL `deploy/cloud/001_...` ~ `008_...`은 로그인·예배 입력·곡/원본·작업 큐·암호화 OneDrive 연결 테이블을 구성한다.

**기존 프로젝트에 똑같은 이름의 임시 Cloud Run 서비스를 추가하고 운영 서비스 계정/Secret Manager 접근을 복제하면 절대로 격리 스테이징이 아니다.** 기존 Cloud Run tagged revision도 Host/Origin 검사 때문에 제대로 접근되지 않을 수 있다.

## 선택된 안전 기준: 완전 별도 테스트 계정

다음 항목을 다른 실제 교회 업무 데이터와 공유하지 않는다. 생성은 비용/계정 관리 승인 뒤 별도 작업이다.

| 분리 대상 | 요구 조건 |
|---|---|
| GCP | **새 테스트 전용 GCP 프로젝트**, 별도 웹·Worker 실행 계정, Secret Manager, Cloud Run 서비스/Job, 테스트 이미지 저장소. `MEDIA_GCP_PROJECT` 값을 반드시 명시해 원래 프로젝트 기본값에 의존하지 않는다 |
| Supabase | 교회 운영과 다른 새 Supabase 프로젝트, 새 공개 키·서버 키, 가상의 승인 팀원 계정, 테스트 전용 `media_members`/작업 데이터. 마이그레이션 SQL은 복제 데이터 없이 schema만 적용 |
| Microsoft/OneDrive | **테스트 전용 Microsoft 계정/Drive**와 해당 계정에 제한된 OAuth 앱·연결값. 기존 개인/공유 교회 드라이브와 분리. 폴더 이름만 다른 경우는 실제 접근권한까지 분리됐다고 보지 않는다 |
| URL/권한 | `MEDIA_PUBLIC_ORIGIN`은 실제 별도 스테이징 호스트와 일치. `MEDIA_WORKER_RESOURCE`는 테스트 프로젝트 Job만 가리키며 운영 `media-production`에 대한 jobsExecutor 권한 없음 |
| Secret Manager | 새 테스트 프로젝트의 테스트 키만; 운영 `church-media-supabase` 또는 원래 OneDrive 키 **값 복사 금지**, 계정에 원래 프로젝트의 secretAccessor 부여 금지 |
| 생성 자산 | 공개 가능한 합성 예배 안내/자체 제작 예시 PPT, 허락된 테스트 악보·MP4·가짜 본문 등. 실제 교회 예배 안내·개역개정 라이선스/원본·검수 전 악보를 마음대로 복제하지 않음 |

별도 테스트 GCP 프로젝트에서 동일한 **비밀 이름**을 사용할 수는 있지만, 실제 값은 그 프로젝트만의 새 자격증명이어야 한다. 프로덕션 URL/프로덕션 Supabase key/OneDrive 계정을 참조하면 즉시 중단한다.

## 실제 테스트를 실행하기 전 필수 가드

1. 새 프로젝트의 Cloud Run 서비스 및 제작 Job의 실행 계정에 기존 운영 프로젝트 Secret Manager, Artifact Registry, 운영 Job 접근 권한이 없음을 확인한다.
2. 비밀 값이나 OAuth 토큰을 출력하지 않고, **새 테스트 Supabase URL/프로젝트 참조만** 표시하여 프로덕션과 다름을 확인한다.
3. Microsoft 연결은 **테스트 전용 계정**으로만 로그인하고, OneDrive에서 새로 생성한 식별 가능한 테스트 파일/폴더만 목록 조회한다. 기존 원본/완료본 저장 폴더에 `write` 시도 금지.
4. 운영 `media-automation` 웹 리비전/이미지와 `media-production` Job 이미지를 읽기 전용으로 기록한다.
5. 테스트 종료 뒤 생성된 리소스 정리 및 비용 확인 방법까지 확정한다.

## 단계별 시험 계획 (테스트 자료로만)

1. 가상 수요 PPT: 주간 안내/성경 절/템플릿을 넣고 작업 시작→단일 claim→생성→PDF 페이지 렌더→별도 테스트 Drive 결과 업로드→재다운로드 SHA256 비교→사람 검수 대기. 실 개역개정 본문 검증과 별개로 기록.
2. 가상 주일 PDF: A4 가로 2면(왼쪽 4/오른쪽 1, 왼쪽 2/오른쪽 3)의 접지 구성·잘림을 화면으로 확인하고 테스트 드라이브 보관.
3. 가상 금요 Zoom/대면: Zoom MP4/MP3 실제 PowerPoint 재생은 **테스트 PC에서 별도**. 대면은 악보 원본 화면을 사용.
4. 2개 테스트 회원의 동시 수정: revision CAS 충돌이 표시되고 서로의 데이터가 자동 덮어써지지 않음.
5. 네트워크/응답 오류, 실패 후 중복 제작, 결과 업로드 일부 성공: 원격 고아 파일과 중복 결과물이 남는지 검사하고, 사람 확인 없는 삭제·덮어쓰기·자동 재시도 금지.
6. 테스트 종료: 대조한 파일 해시·서버/Job digest·작업 로그(비밀 제외)를 남긴 뒤 리소스 정리. 실제 운영 반영은 별도 승인.

## 지금 자동으로 실행하지 않는 명령

- `deploy/cloud/deploy-runtime.sh`: 지금까지 확인된 설정은 **운영 환경을 직접 변경**하므로 독립 스테이징에 사용하지 않는다.
- `gcloud run jobs execute media-production`: 운영 제작 Job 실행이므로 테스트에 사용하지 않는다.
- `gcloud run services update-traffic media-automation`: 운영 트래픽 변경.
- 운영 Supabase 데이터 삭제/재이관/스키마 변경, OneDrive 원본 삭제·덮어쓰기.

## 비용/준비 미확정 사항

별도 Supabase와 Microsoft 테스트 계정/OneDrive Drive의 준비 여부, 별도 Google 프로젝트 생성 승인, 프로젝트별 청구 정책은 아직 확인되지 않았다. 특히 **GCP 예산 경보가 실제 지출 상한이 아님**을 감안하고 소규모로 시작한다.

다음 작업의 안전한 출발점은 **새 테스트 리소스가 운영 계정에 연결되지 않는지 확인하는 접근 권한 검수**이며, 운영 서버에 새 비밀 권한을 부여하거나 본문/자료를 자동 복제하지 않는다.
