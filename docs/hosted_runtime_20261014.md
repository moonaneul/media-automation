# 클라우드 제작 연결 — 2026-10-14

코드 검토: https://github.com/moonaneul/media-automation/pull/14

## 실제 적용 결과

SQL 007, 주보 공통자료 추가 매핑을 적용했고 SQL 008의 전체 rollback 검증이 성공했다. 저장 입력 13개·곡 44개는 유지되며 파일 69개·공통자료 경로 28개다. 웹과 제작 Job을 asia-northeast3에 비공개 배포했다. 최신 코드 이미지의 digest는 `sha256:31cd19c5894929d75c79e52f29462a6e3ba36677fc05f5a0e4a442f4d4a4decf`, 웹 revision은 `media-automation-00002-jck`이다. 기존 Office/한글/SDK 이미지 계층을 재사용했다.

실제 저장 입력으로 수요 PPT 36장과 주보 A4 가로 PDF 2면을 각각 생성했다. 전체 렌더링, OneDrive 새 결과 보관, 재다운로드 SHA256 검증이 성공했다. 수요 실행은 1분 26초였다. 로컬 서버를 재시작하거나 원본·DB·인증 파일을 변경하지 않았다.

렌더링 화면 검수에서 수요 시험 입력의 악보 3개 미연결, 다른 곡 첨부 1개, 두 자리 절 번호의 줄바꿈을 발견했다. 주보는 4|1·2|3 접지 배치와 여백을 확인했으며 미입력 인도자 1개를 검수 항목으로 남겼다. 과거 시험 입력을 임의 수정하지 않았고 두 결과 모두 예배용 완료 처리는 하지 않았다.

실제 웹에서 비로그인 자료 조회·제작 요청은 401, 다른 Origin 제작 요청은 403으로 차단했다. 2026-10-15 사용자 진행 승인 후 웹 서비스에만 외부 접속을 허용했다. 공개 로그인 화면 200 및 비로그인 자료 조회 401을 확인했으며 제작 Job 권한은 변경하지 않았다. Supabase 실제 사용자 로그인·입력 불러오기·웹 dispatch·결과 저장·미리보기·다운로드까지 확인했다. 다른 기기·Mac-off 사용, 금요 미디어 재생은 미검증이다. `/healthz`는 외부 Google 응답에서 404를 반환했으므로 외부 health 판정에 사용하지 않는다. `/api/mode`와 Cloud Run revision ready는 확인했다.

## 이번 변경

기존 화면을 유지하면서 별도 Cloud Run HTTP/제작 entrypoint를 추가했다. 로컬 서버는 기존 경로를 사용하고, hosted 경로는 Supabase 장애 때 SQLite로 대체 저장하지 않는다.

- 웹: Supabase 팀 권한을 매 요청 확인하고, 공유 저장소에 암호화한 서버 세션을 둔다. 브라우저에는 무작위 HttpOnly/Secure/SameSiteStrict 쿠키만 전달한다. 1시간 세션과 upstream 인증 만료 때 재로그인한다. refresh token은 저장하지 않는다.
- 입력: 기존 저장 버전 비교·수정 이력 RPC를 사용한다.
- 목록: 곡·원본 관계·검수·첨부·주보 설정을 명시적인 작업 RPC로 수정하며 공통 목록 버전을 비교한다.
- 파일: 128MB까지 Microsoft 분할 업로드를 사용한다. 임시 업로드 권한은 특정 새 파일에만 적용하고 서버 OAuth 토큰은 브라우저에 보내지 않는다. 업로드를 마치면 서버가 원본 폴더·크기·SHA256을 검증한다.
- 제작: 사용자 요청의 UUID만 고정된 Cloud Run Job에 전달한다. 이미지·명령·임의 환경 변수는 요청으로 받지 않는다. DB에서 dispatch/claim을 한 번만 허용한다. 요청의 입력·목록 snapshot을 사용하고 필요한 원본만 가져온다.
- 결과: PPT/PDF 생성, 전체 PDF 페이지 렌더링, 새 결과의 OneDrive 업로드와 다운로드 해시 검증 뒤 DB finish를 호출한다. 생성 성공과 사람이 화면·재생을 검수한 완료 상태는 분리한다.
- 취소·시간 만료·권한 철회: 작업 활성 상태를 확인하고 완료 저장을 거부한다. 실행 중인 LibreOffice 같은 외부 프로세스는 호출 제한 시간까지 동작할 수 있다. 자동 실행 재시도는 하지 않는다.
- 다른 기기: Supabase에 남은 성공 결과로 입력 화면의 파일 링크를 복원하고, 해당 주 제작 기록도 조회한다. 로컬 생성 파일에 의존하지 않는다.
- 교회 지침: 미입력 찬양 인도자·기도 담당자·설교자와 주보 호수 자동 채움을 제거했다. 값은 확정 입력으로 사용하며 없으면 비워 두고 검수 항목으로 보고한다. 기존 원본은 변경하지 않았다.

## 새 주보 공통자료

기존 공통자료 목록 25개에는 주보 원본 템플릿·글꼴이 없었다. 기존 OneDrive 선택 원본 폴더 아래 `제작 공통 자료`에 아래 3개를 추가했다.

- original-design.pdf
- original-regular.ttf
- original-bold.ttf

새 파일 3개만 다운로드 SHA256을 검증했다. 이전에 검증한 원본 전체는 다시 해시하지 않았다. 추가 매핑 SQL은 프로젝트 작업 폴더의 `output/cloud-bulletin-runtime-20261014/register_bulletin_runtime.sql`에 보관하며 Supabase 적용을 완료했다. 실제 자산·파일 ID 매핑·DB·인증파일은 GitHub에 올리지 않는다.

## 검증과 한계

- 준비 코드 관련 테스트 112개 확인.
- 전체 회귀 실행: 812개 통과, 1개 skip, 1개는 작업 복사본에 의도적으로 제외한 주보 표지 이미지가 없어 실패했다. 표지를 시험 폴더에만 복사한 후 해당 테스트 통과. 공개 코드에는 포함하지 않았다.
- 마지막 담당자·클라우드 화면·제작 흐름 변경의 관련 테스트 93개 통과.
- 새 SQL 007과 rollback 시험 SQL 008: PostgreSQL SQL 및 PL/pgSQL 파서 문법 검사와 실제 DB rollback 시험 통과.
- Python/JavaScript 문법과 diff 공백 검사 통과.
- 단위 테스트는 모의 환경을 사용한다. 별도로 실제 PPT/PDF 클라우드 생성·렌더링·보관·화면 검수를 수행했다. PowerPoint 정상 열림·금요 미디어 재생·Mac-off 운영은 확인하지 않았다.
- 웹의 기존 OneDrive 조회·원본 선택·자동 연결·보관 자료 다운로드는 연결했다. hosted 운영의 Microsoft 재연결/앱 인증 설정/선택 폴더 변경 화면은 제한한다. 기존 연결의 실제 갱신/유지 검증을 먼저 하고 관리자 재연결 운영 절차를 보완해야 한다.
- 브라우저 통합 검증을 완료했다. 금요 미디어·PowerPoint 및 실제 운영 전환 검수가 남아 PR은 초안으로 유지한다.

## 실제 적용 순서

1. Supabase 전용 church-media에 `007_hosted_runtime.sql` 적용. 이는 브라우저 비밀정보 접근을 막는 session 테이블과, 승인 팀원의 목록 수정/완료 확인·취소 RPC를 추가한다.
2. 추가 주보 매핑 SQL 적용. 기존 공통자료 경로가 다른 digest로 등록돼 있으면 실패하고 덮어쓰지 않는다.
3. `008_verify_hosted_runtime.sql` 실행. 가상 입력·곡·큐만 만들고 전체 rollback한다. 실제 제작 중인 작업이 있으면 중단하고 나중에 실행한다. 별도 Cloud Run 실행·OneDrive 쓰기는 하지 않는다.
4. 코드 전용 패키지로 `Dockerfile.runtime` 이미지 빌드. 검토한 image digest만 배포 스크립트에 전달한다. 기존 probe 이미지를 웹/worker로 사용하지 않는다.
5. 별도 `media-web` 실행 계정에 기존 Supabase 비밀과 OneDrive 암호화키 읽기를 부여하고, `media-production` Job 한 개에만 실행 권한을 준다. worker는 기존 `media-runtime` 계정을 사용한다. Google Secret Manager에 새 키/버전은 만들지 않는다.
6. 웹은 일단 Google 인증이 필요한 비공개 상태로 배포한다. 서비스 응답과 DB 권한을 확인한 뒤 로그인 페이지 외부 공개를 별도로 적용한다. 작업 데이터는 Supabase 로그인과 승인 팀원 권한이 있어야 접근할 수 있다.
7. 수요 PPT → 주보 PDF → 금요 순으로 실제 시험한다. SQL/CAS·비인가·중복·실패·취소·만료·권한 철회, 한글/절/악보/여백, 실제 사용 시간·메모리·출력 크기를 확인한다. 금요 내장 미디어 존재와 PowerPoint 실제 재생은 별도다.
8. 다른 기기 로그인·저장·제작·결과 다운로드, Mac-off 사용, 마지막 로컬/클라우드 입력 차이를 확인한다. 전환 확인 전 8876 서버·로컬 전체 저장소는 유지한다.

## 배포 검토 값

| 항목 | 준비한 값 |
|---|---|
| Google 프로젝트/지역 | church-media-511519 / asia-northeast3 |
| 웹 서비스 | media-automation |
| 제작 Job | media-production |
| 웹 실행 계정 | media-web@church-media-511519.iam.gserviceaccount.com |
| worker 계정 | 기존 media-runtime |
| 웹 크기 | CPU 1 / RAM 2Gi / 요청 동시수 1 / 최소 인스턴스 0 / 최대 1 / 제한 300초 |
| worker 크기 | CPU 1 / RAM 4Gi / task 1 / parallelism 1 / 자동 재시도 0 / 제한 840초 |
| DB 제작 deadline | 기존 15분 |
| 출력 제한 | 파일당 512MB, PPT 최대 500장 |
| 원본 제한 | 파일당 128MB, 한 제작 임시 원본 합계 768MB |

이 설정이 무료를 보장하지 않는다. 기존 1,000원 예산은 알림이다. 대형 Registry 이미지 저장·Secret Manager 버전·실제 실행·외부 전송을 배포 후 확인해야 한다.

기준 문서: [Google Job 실행](https://docs.cloud.google.com/run/docs/execute/jobs), [Job 실행 권한](https://docs.cloud.google.com/iam/docs/roles-permissions/run), [서비스 URL](https://docs.cloud.google.com/run/docs/triggering/https-request), [최소 인스턴스](https://docs.cloud.google.com/run/docs/configuring/min-instances), [Microsoft 분할 업로드](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0).

Cloud Run의 큰 HTTP 응답 제한에 대응해 hosted 다운로드를 명시적인 HTTP/1.1 chunked 전송으로 추가했고 정확한 바이트 전송/실패 처리 관련 테스트 21개가 통과했다. 최신 빌드는 Registry/Cloud Run과 같은 asia-northeast3 지역에서 수행했다. 저장된 과거 입력은 제작 시험에만 사용하고 이번 주 값을 대체하지 않는다.

## 2026-10-15 브라우저 통합 검증

승인 계정 로그인 후 공동 입력을 불러오고 기존 결과를 다운로드해 SHA256 일치를 확인했다. 웹에서 요청한 새 PPT 36장 제작이 성공했고, 제작 요청 202·공동 결과 저장 200·보고서와 미리보기 200을 실제 서버 기록에서 확인했다.

이 과정에서 이전 로컬 파일 ID가 미리보기에 남는 문제와 자동 새로고침 중 제작 요청이 보류되는 문제를 수정했다. 완료 검수된 기존 결과는 유지하고 입력이 일치하는 클라우드 결과를 복원하며, 제작 전에는 진행 중인 입력 새로고침을 기다린다. 관련 검사 79개가 통과했다.

웹 revision `media-automation-00003-4s8`, 코드 `82812db`, 이미지 `sha256:da68818b0075f27d77df6789f8a296a9addb8425781ac1c9e10189d039811b4c`를 배포했다. worker 이미지는 이전 검증판을 유지했다. CPU·메모리·인스턴스 제한·새로고침 주기는 변경하지 않았다. 현재 로그인은 만료됐으므로 다시 사용하려면 재로그인이 필요하다.
