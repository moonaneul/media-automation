# media-automation 인수인계 — 2026-10-14

## 바로 이어갈 목표

사용자는 한 개의 media-automation으로 어디서나 접속하고, Mac이 꺼져도 예배 PPT·주보 PDF를 제작하기 원한다. 개인 OneDrive는 원본·완료본 저장, Supabase는 로그인·입력·목록·작업 상태, Google Cloud Run은 웹/API와 별도 제작 작업을 맡는다. Vercel은 현재 구성에 없다. 카드 등록은 가능하지만 실제 비용은 최대한 0원을 지향한다. 현재는 연결 준비 완료이며 공개 웹사이트와 실제 클라우드 제작은 미완성이다.

사용자는 짧고 구체적인 안내와 자율 진행을 선호한다. 완료된 자료 비교·해시 검사는 반복하지 않는다. 비밀번호·서버 Secret key·OAuth 토큰은 채팅에 요청하거나 출력하지 않는다. sources/와 기존 원본은 읽기 전용이다. 교회 제작 규칙은 AGENTS.md를 읽고 따른다.

## GitHub와 로컬 비교 — 이번에 직접 확인

- 저장소: https://github.com/moonaneul/media-automation
- GitHub main과 로컬 HEAD 모두 `85e4c5dfa69549311dc5aae1bc24deac836dc5e8` (PR #13 병합). git ls-remote로 현재 원격 확인.
- 따라서 커밋 기준 차이는 0. 하지만 최신 로그인·클라우드·단일 실행기 코드는 미커밋 상태로 로컬에만 있다.
- 문서 갱신 전: 추적 파일 수정 9개, 미추적 파일 53개. 미추적 53개 중 주보 자산 6개 포함. 문서 갱신 뒤 수치는 늘어날 수 있다.
- 주요 수정: README, pyproject, run_original_blue, generation, onedrive, 원본 server/UI, web/server, fault-injection test.
- 주요 새 파일: cloud/ 모듈 12개, deploy/cloud/ SQL·설정·Docker, start.command/start_primary, 이관·OneDrive 업로드 스크립트, 관련 테스트.
- assets/bulletin/cover_autumn.jpg는 실제 HWP에서 추출한 교회 표지·연락처 포함 자산. 다른 PNG도 공개 포함 여부를 따로 판단해야 한다. `git add .`로 일괄 올리지 않는다.
- 원격 main은 최신임을 확인했지만 PR 열림/닫힘 상태는 조회하지 않았다. 예전 로컬 브랜치 ahead/behind는 마지막 fetch 기준이므로 최신 원격 판정으로 사용하지 않는다.
- 이번에는 커밋·push·PR 생성·원격 브랜치 삭제를 하지 않았다. 미커밋 변경의 코드 전용 보관 파일을 별도로 제공한다.

## 실사용 로컬

- 기준 폴더: /Users/moonaneul/Documents/media-automation
- 실행: start.command → scripts/start_primary.py. 기본 Supabase 이메일 로그인.
- 주소: http://127.0.0.1:8876/ . 이번 확인 시 Python PID 50289, loopback LISTEN. 서버 재시작/종료하지 않았다. PID는 고정값이 아니다.
- DB 지정: output/main-database.txt
- 실제 DB: /Users/moonaneul/Documents/media-automation/output/main-store-20261013-145218/work.db
- DB 읽기 전용 quick_check=ok.
- works13, songs44, song_assets46, attachments27, asset_reviews3, bulletin_settings1, cloud_song_sources40, cloud_auto_sources44, cloud_archives4.
- 8876의 저장은 여전히 SQLite, OneDrive 연결은 기존 로컬 암호화 저장소이다. 클라우드의 Supabase 복사본과 자동 동기화되지 않는다. 이후 로컬 수정이 있었다면 전환 직전 차이를 대조해야 하며 단순 재이관/덮어쓰기 금지.
- 실사용 work.db, work.files, work.generated, work.onedrive/connection.enc 및 encryption.key 등 전체 저장소를 함께 보존한다. 인증 파일은 공유용 인수인계/코드 ZIP에 넣지 않는다.

## 완료한 클라우드 준비 — 사용자 실행 결과 기준

Google 프로젝트 church-media-511519, 번호626807737784, 서울 asia-northeast3. 결제 연결됨. 1,000원 예산은 알림이며 결제 차단 상한이 아니다.

Supabase 전용 church-media 프로젝트:
- URL https://rzqvhldujuaeqnckxezw.supabase.co (공개 설정은 deploy/cloud/supabase-public.json)
- 지역 싱가포르 ap-southeast-1. 기존 다른 프로젝트 수정 금지.
- 관리자 UID 776e30f7-9dd3-4229-b9d4-23de72331f21, media_members admin/active.
- 이메일 로그인/권한 확인 성공. 공개 가입으로 팀 권한을 자동 부여하지 않는다.
- 작업 저장·충돌·수정 이력·권한 SQL 설치 및 검증 성공.
- 입력13개 복사 SQL 사용자 완료 보고. 목록44곡/48파일/46관계/27첨부/3검수/1주보설정/4보관기록 복사 완료 보고.
- 추가 공통자료25경로·새파일18개, 총 고유66파일을 위한 setup_cloud_production.sql 사용자 성공 문구 확인.
- 적용 SQL005: runtime_assets, 일관된 입력/목록 snapshot, 요청 중복 방지/전역 큐, worker claim/finish 권한.
- SQL006: media_connections 암호문 저장, 브라우저 접근 금지, service_role만 읽기/추가/갱신.
- 실제 원격 DB 전체 행과 현재 로컬 DB의 재대조는 아직 하지 않았다. 이관 당시 SQL은 기존 값이 다르면 덮어쓰지 않고 실패하도록 작성됐다.

OneDrive:
- 개인 Microsoft 계정. 기존 선택 원본/완료본 폴더 활용.
- 누락 원본8개와 추가 공통 제작자료18개 업로드; 새 파일은 다운로드 SHA256 대조 통과. 총 공통 제작 경로25개(같은 내용 재사용 포함).
- 공통자료는 선택 원본 폴더 아래 ‘제작 공통 자료’에 위치. 기존 파일 덮어쓰지 않았다.
- 기존 보유 자료 전체 이전이 아니라 실제 필요한 자료만 점진 등록.

Google 실행 계정: media-runtime@church-media-511519.iam.gserviceaccount.com
Google Secret Manager:
- church-media-onedrive: 이전 로컬 연결 정보를 안전하게 가져온 bootstrap JSON.
- church-media-supabase: 사용자 직접 생성한 sb_secret_ 서버 키. runtime에 accessor 부여 완료.
- church-media-onedrive-key: 자동 생성한 Fernet 키, version1. runtime accessor 부여 완료. 새 키로 덮어쓰면 기존 암호문 복호화 불가.
- 갱신 OneDrive 연결은 Supabase에 암호화하고 revision CAS로 저장. Google 비밀 버전을 매번 늘리지 않는다.
- bootstrap 비밀에는 과거 부여한 secretVersionAdder가 남아 있다. 최종 런타임에서 불필요함을 확인 후 권한 제거 후보.

성공한 Google Jobs:
1. media-runtime-probe / media-runtime-probe-sndnt: 제작환경 검사. Cloud Shell에서 합성 한글 PPT→PDF/한글 텍스트 확인도 성공.
2. media-onedrive-probe / media-onedrive-probe-fbkk4: 실행 계정으로 원본·완료본 폴더 접근.
3. media-backend-check / media-backend-check-2cn7s: 2026-10-14 사용자 로그에서 성공. 코드의 종료0 조건은 Supabase 서버 접근, OneDrive 암호화 연결 초기화/복호화, 두 폴더 접근, 익명 연결 정보 접근 차단 모두 통과.

최신 확인 이미지:
asia-northeast3-docker.pkg.dev/church-media-511519/church-media/backend-check:20261014
sha256:50cca63a6d66186582512d3cc801329a812719b315d55ab8987e40b70a12e57b
기본 이미지 runtime-cloud:20261014-v2 digest 8a94553f9259a798debc1c5bdb7aacd22cd4a8f3f7e8491cb9dcbaf2f2a325d4.
backend-check는 확인 후 종료하는 이미지다. 웹서비스/실제 제작 worker로 그대로 배포하지 않는다.

## 남은 작업 — 권장 순서

1. 최신 코드 보존 및 GitHub 반영: 코드·테스트·문서만 명시적으로 선별, 실제 자산/DB/키/전달 암호파일 제외. 문서의 과거 ‘미실행’ 기록보다 최신 상태 요약 우선. 코드 기능별 검토 후 commit/PR.
2. 클라우드 HTTP 진입점과 저장 연결: 현재 web/server.py는 여전히 WorkStore(SQLite), OneDrive(store), loopback server이다. SupabaseWorkStore/JobClient는 존재하지만 실사용 UI/API에 연결되지 않았다. 원본/곡목록·검수·첨부·주보설정 등록/수정도 클라우드 경로 필요(현재 catalog 테이블은 팀원 읽기만 허용). 기존 UI 기능 손실 없이 연결.
3. 로그인 세션 운영 설계: 현재 upstream JWT는 서버 메모리, 브라우저에는 opaque HttpOnly SameSiteStrict 쿠키. 재시작/다중 인스턴스에서 세션 유지 전략과 만료/재로그인 UX, HTTPS/public origin/CSRF를 구현·검증. PORT,0.0.0.0 대응 필요. 서버 비밀키/암호화키 브라우저 노출 금지.
4. 실제 제작 worker: DB claim→고정 snapshot→필요 원본만 OneDrive 다운로드·해시 확인→기존 엔진 PPT/PDF 제작→완료본 OneDrive 업로드 검증→finish. snapshot.materialize/JobBackend는 준비됐지만 실행 main·결과 업로드/다운로드 연결은 미완성.
5. Cloud Run Jobs 호출 dispatcher/API와 최소 IAM: 사용자 확인된 요청만 실행, 임의 이미지/명령/env 요청 금지. 중복 클릭/실행 실패/시간 만료/취소·권한 취소를 다루고 성공한 완료본만 UI 노출. 전역 큐와 CAS가 실제 요청 흐름에서 유지되는지 검증.
6. 원격 상태 확인: 이관13개+metadata/runtime66개를 읽어 대조, 실제 큐 start/claim/finish와 비인가/충돌/실패 테스트. 완료된 원본 전체를 다시 해시하지 말고 변경분과 필요한 결과만 검증.
7. 실제 제작 순차 시험: 수요 PPT→주보 PDF→영상 포함 금요 Zoom/대면. 한글/원본 슬라이드/본문/레이아웃 실제 렌더링 검수. 미디어 존재와 PowerPoint 재생은 별도. 시간·메모리·출력 크기 측정.
8. 웹 공개 배포: 최소 인스턴스0, 제작자동재시도0·동시수 제한·타임아웃·입력/파일 크기 제한, 실제 사용량/저장/외부 전송 비용 확인. 다른 기기에서 로그인/저장/제작/완료본 다운로드까지 시험하고 Mac-off 사용 확인 후 전환 완료 선언.
9. 마지막 로컬/클라우드 차이 확인 및 정리. 기존 DB와 원본은 전환 검증 전 유지.

현재 불확실성: 전체 실제 예배 자료 클라우드 제작·렌더링/실재생·외부 웹 접속·Mac-off 제작은 미검증. 무료 보장하지 않는다. SecretManager enabled/disabled 버전 모두 비용 대상이므로 무한 버전 추가 금지. Registry 대형 이미지가 있어 저장 무료분 초과 여부 확인 필요.

## 정리 후보 — 이번에는 삭제하지 않음

실사용 media-automation 약18GB: output 약10GB, .git 약6.9GB(그중 LFS6.8GB), assets341MB,input166MB,.venv222MB. 실사용 출력은 결과/원본/연결정보 포함이므로 통째로 삭제 금지.

보조:
- media-automation-blue-original 약7.5GB, output7.1GB. detached531ca67, 추적/미추적 코드 변경0.
- media-automation-blue-test 약7.5GB, output7.1GB. detached87cbb09, 코드 변경0.
- media-pr11-check 약21GB, review output10GB+selection output10GB. detached0bfec73, 코드 변경0.
- media-backup-20261013-100807 약7.5GB: 원본 백업. 위3개 작업트리와 합계 약43.5GB지만 전량 회수 가능하다고 확정하지 않음.
- media-archive-20261013 약289MB: 이전 ZIP/코드 보관. 우선 유지.

검토용 work.db 두개는 현재 DB와 전체 works 행 해시가 다르다. 입력내용·선택상태·시간 차이를 별도로 보존 후 정리해야 한다. 코드 변경0은 무시된 출력/DB/비밀파일의 동일함을 의미하지 않는다. 세 작업폴더는 등록된 Git worktree이므로 Finder 강제 삭제보다 Git worktree 절차를 사용한다. 백업/필요 원본·DB·인증자료 보존 검증을 먼저 한다. LFS 캐시는 Git 객체 자체37MB와 다르며 무작정 .git 삭제 금지. 원격 LFS 보존 여부와 로컬 참조 검증 후 prune 여부 판단.

완료 후 정리 후보: Mac output/cloud-transfer/*.enc 및 Cloud Shell 전달 암호파일·이전 압축/빌드 폴더. 현재 사용중 work.onedrive/encryption.key/connection.enc와 Google 암호화키는 삭제 금지. 비밀이 들어 있는 백업도 공개 업로드 금지.

## 검증 증거 및 파일

이번 상태 점검: 대상 모듈 테스트76개 통과, 로컬 socket 제한으로 실행 불가했던 로그인8개를 별도 권한으로 재실행 모두 통과. 합계84개. backend probe 모의검증3개는 직전 단계 통과. 기존 전체697통과/1skip은 이전 시점 결과이며 최신 전체 suite 결과로 주장하지 않는다. PyMuPDF 경고5개는 기존 deprecation이다.

작업공간:
/Users/moonaneul/.codex/.chatgpt-projects/g-p-6ab72da419408191aaefdbdcf376f14e
- output/cloud-work-migration-20261014/import_13_works.sql
- output/cloud-asset-migration-20261014/import_library_metadata.sql
- output/cloud-asset-migration-20261014/onedrive-added-originals.json
- output/cloud-runtime-assets-20261014/runtime-assets.json
- output/cloud-runtime-assets-20261014/setup_cloud_production.sql
- output/cloud-runtime-assets-20261014/production-setup-manifest.json
- output/cloud-backend-probe-20261014/test_backend_probe.py
- review-results/media-backend-check-20261014.tar.gz (코드전용, Dockerfile 포함)

코드 중요 지점: cloud/supabase_auth.py, supabase_work_store.py, snapshot.py, job_api.py, encrypted_connection.py, runtime_secrets.py, backend_probe.py. generation.py의 ensure_original hook만 cloud snapshot에 선택적으로 적용됨. 정식 Cloud Run HTTP/worker entrypoint 아직 없음.

다음 채팅 첫 지시 예시: ‘이 인수인계 기준으로 최신 코드 GitHub 반영과 클라우드 웹/API·실제 제작 worker 연결을 계속 진행해. 기존8876과 원본/DB는 유지하고 완료한 이관·해시 검사는 반복하지 마.’
