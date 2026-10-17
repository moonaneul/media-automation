> **현재 구현:** [클라우드 제작 연결 기록](../../docs/hosted_runtime_20261014.md). HTTP/worker entrypoint는 추가됐으며 SQL 007/008와 실제 Cloud Run 적용은 검증 전입니다. 기존 probe 이미지는 production 배포에 사용하지 않습니다.

> **2026-10-14 최신 상태:** 로컬 8876은 Supabase 로그인 + 기존 SQLite로 운영 중입니다. Supabase 입력·목록·공통 자료 설정 적용과 Google 서버의 Supabase/암호화 OneDrive 연결 검사는 완료했습니다. Cloud Run 공개 웹서비스와 실제 제작 worker는 아직 미완성입니다. 최신 로컬 변경은 아직 GitHub에 커밋되지 않았습니다. 아래 과거 진행 기록의 ‘아직 미실행’ 표현은 당시 상태입니다. 다음 작업과 정리 기준은 [최신 인수인계](../../docs/cloud_handoff_20261014.md)를 우선 참고하세요.

# OneDrive + Supabase + Cloud Run

선택한 구성의 준비 단계다. 현재 로컬 앱은 계속 사용한다. 이 폴더가 있다고 공개 배포 가능한 상태는 아니다.

## 역할

- Cloud Run Service: 웹 화면과 API. Supabase 로그인 토큰 및 팀원 권한을 서버에서 검증한다.
- Supabase: 로그인, 허용 팀원 목록, 날짜/예배별 입력, 수정 버전, 제작 작업 상태, OneDrive 파일 ID.
- Cloud Run Jobs: 저장된 입력의 특정 버전을 받아 PPT/PDF를 생성하는 별도 프로세스.
- OneDrive: 원본과 결과 파일. DB 파일 자체를 OneDrive에 동기화해 공동 사용하지 않는다.

화면과 제작기는 같은 media-automation 코드에서 관리한다. 사용자에게는 웹 주소 하나만 제공한다.

## 이번에 준비한 것

Dockerfile은 Linux/Python, LibreOffice, Poppler, FFmpeg, 한글 글꼴을 포함한 **환경 확인용**이다.
기본 실행은 필요한 모듈·실행 파일·한글 글꼴 확인 후 종료하며 웹 포트를 열거나 실제 예배를 제작하지 않는다.
입력/자료/DB/로컬 인증 폴더를 이미지에 복사하지 않는다. 빌드 컨텍스트도 Dockerfile 전용 allowlist로 제한한다.
계정 생성, 클라우드 이미지 빌드, 업로드, 리소스 생성, SQL 적용은 아직 수행하지 않았다.
Docker CLI가 이 Mac에서 확인되지 않아 실제 이미지 빌드는 미검증이다.

프로젝트 루트에서 로컬 시험(Docker 설치된 환경):

```sh
docker build --platform linux/amd64 -f deploy/cloud/Dockerfile -t media-runtime-probe .
docker run --rm --network none media-runtime-probe
```

클라우드 이미지 빌드도 CPU·이미지 저장 비용이 발생할 수 있다. 프로젝트와 비용 설정을 확인한 후 실행한다.
환경 확인이 통과해도 실제 제작 시간·메모리·미리보기·폰트 결과 검증은 별도다.

## 계정 정보가 정해진 다음 구현할 일

1. Supabase 로그인 및 승인된 미디어팀만 접근하도록 권한 구현. 가입만으로 팀원 권한을 주지 않음.
2. SQLite의 수정 버전 충돌 검사를 PostgreSQL 트랜잭션으로 옮기고 13개 예배 입력/첨부 매핑을 검증 이관. 기존 DB 유지.
3. OneDrive 계정 유형 확인. 기존 코드는 개인 계정용 consumers authority이며 로컬 암호화 파일에 토큰을 저장함.
   Cloud Run 임시 디스크에 토큰과 암호화 키를 영구 저장하지 않음. Secret Manager 등 서버 전용 저장 설계 필요.
4. 현재 파일 경로 첨부를 OneDrive의 drive/item ID와 내용 해시로 연결. 파일 다운로드·제작·결과 업로드 작업 구현.
5. 작업 요청은 로그인과 권한을 확인한 API만 생성. 작업자는 DB에서 입력 버전을 고정하고, 제작 후 OneDrive 저장 성공을 확인한 뒤 완료 상태 기록.
6. Cloud Run HTTP 진입점 구현: PORT 수신과 0.0.0.0 바인딩, HTTPS 원본/인증 검증. 현재 로컬 전용 서버를 그대로 공개하지 않음.

## 비용 시험 기본값(배포 미실행)

- 웹: 최소 인스턴스 0. 요청 기반 과금 후보.
- 제작 시험: 작업당 task 1, parallelism 1, max retries 0, timeout 10분, 1 CPU/2GiB부터 측정.
- parallelism 1은 한 실행 내 제한이다. 여러 실행이 동시에 생성되는 것을 막으려면 DB의 원자적 작업 잠금과 중복 요청 키가 별도로 필요하다.
- 제작 제한시간 초과·실패 시 자동 반복 실행하지 않음. 작업 횟수/원본 크기 제한과 명시적 재시도 구현.
- OneDrive로 결과를 보내는 Cloud Run 외부 전송량, 이미지 저장, 빌드, 로그, 비밀 저장 비용을 함께 측정.
- 예산 알림은 비용 상한이 아니다. 서비스별 적용 가능한 비용 제한을 확인하며 0원 보장은 하지 않음.
- 기존 OneDrive 구독 용량을 활용한다는 전제이며 추가 용량 비용은 별도.

## 실제 제작 시험 순서

환경 확인 → 수요 PPT → 주보 PDF → 영상 포함 금요 PPT.
각 단계의 시간·최대 메모리·입출력 크기·예상 월 횟수를 기록해 무료 범위 적합성을 평가한다.
실제 교회 자료 업로드는 대상 프로젝트와 저장 위치를 확정한 뒤 수행한다.

공식 참고:
- https://docs.cloud.google.com/run/docs/container-contract
- https://cloud.google.com/run/docs/create-jobs
- https://cloud.google.com/run/pricing
- https://supabase.com/docs/guides/database/postgres/row-level-security

## 사용자 확인 사항

- OneDrive: 개인 Microsoft 계정. 기존 개인용 연결 코드 활용 대상.
- Supabase: 다른 프로젝트가 있으므로 재사용/수정하지 않고 교회 미디어 앱 전용 프로젝트를 준비.
- Google Cloud 프로젝트 및 결제 계정 준비 여부는 아직 미확인.

## 2026-10-14 인증 연결 진행

Google 프로젝트 church-media-511519에서 runtime-probe 작업이 성공했다. Supabase 전용 프로젝트와 첫 관리자 등록 및 실제 계정 로그인 확인도 완료했다.
공개 설정은 supabase-public.json에 있으며 비밀번호·비밀 키는 없다. MEDIA_AUTH_PROVIDER=supabase 환경변수로 기존 웹 화면의 이메일 로그인 및 서버 측 팀원 검증을 활성화한다. 기본 로컬 실행은 유지한다.
인증 토큰은 서버 메모리에만 보관하고 브라우저에는 HttpOnly 세션 쿠키만 제공한다. 매 요청마다 로그인 및 팀원 승인을 검증한다. 세션은 최대 한 시간이며 토큰 만료 시 다시 로그인한다. 다중 인스턴스용 공유 세션은 아직 미구현이다.
현재는 로컬 검증 단계이며 Cloud Run 웹 배포, PostgreSQL 작업 저장 이관, OneDrive 영구 자격 증명 및 제작 작업 연결은 남아 있다. 실행 중인 8876 서버에는 새 로그인 설정을 적용하지 않았다.

2026-10-14 로그인 활성화: 사용자의 별도 화면 로그인 확인 후 실사용 8876 서버를 Supabase 인증으로 재시작했다. `scripts/start_primary.py`의 기본 인증은 Supabase이며 기존 DB의 예배 입력 13개 내용과 무결성을 확인했다. 18877 시험 서버는 종료했다. 클라우드 웹 배포는 아직 아니다.

2026-10-14 작업 저장 준비: SupabaseWorkStore 및 날짜/예배별 현재 입력·수정 이력 SQL을 추가했다. 저장 함수는 로그인 팀원 확인과 수정 버전 비교·저장을 한 트랜잭션에서 처리한다. 첫 저장 동시 요청에도 advisory transaction lock을 적용한다. 네트워크 오류 시 자동 재시도·로컬 대체 저장을 하지 않는다. 코드 테스트 33개 통과. `deploy/cloud/setup_work_storage.sql`은 설치와 롤백 시험을 합친 파일이며 Supabase 적용 및 실제 DB 검증은 아직이다. 실사용 8876 저장은 기존 SQLite를 계속 사용하며 13개 입력의 이관은 진행 전이다.

2026-10-14 Supabase 작업 저장 SQL 적용: 사용자가 설치·저장·충돌·수정 이력·권한 검증 성공 화면을 제공했다. 현재 예배 입력 13개를 읽기 전용 SQLite 스냅샷으로 내보냈으며 수정 버전·본문·수정 시각을 그대로 복사하는 SQL을 준비했다. 기존 클라우드 레코드가 다르면 전체 이관을 취소하고 덮어쓰지 않는다. 실제 13개 이관 SQL 실행과 로컬/클라우드 데이터 대조는 아직이다. 첨부 27개·곡 44개·주보 설정 및 OneDrive 매핑은 별도 단계이며 로컬 DB를 계속 보존한다.

2026-10-14 OneDrive 클라우드 준비: 기존 원본/완료본 폴더의 실제 Microsoft Graph 접근을 확인했다. 연결 정보 재설정 없이 Secret Manager에 보관할 선택형 백엔드와 암호화 전달/가져오기 도구를 추가했다. 기존 OneDrive 및 새 기능 테스트 46개 통과. `scripts/export_onedrive_connection.py`는 터미널에서 입력한 새 전달용 암호로 암호화 파일만 생성하며 암호/비밀 값/토큰을 출력하지 않는다. 코드 전용 가져오기 ZIP도 준비했다. Google 비밀 저장소 생성·연결 정보 가져오기는 아직이며, 웹/작업 프로세스 사이 자격 증명 쓰기를 직렬화한 뒤 백엔드를 활성화해야 한다. 현재 8876은 기존 로컬 암호화 연결을 계속 사용한다. 비밀 저장소 버전 정리 및 권한 설정도 실제 배포 전에 완료한다.

2026-10-14 OneDrive 비밀 가져오기 완료: 사용자가 `church-media-511519` 프로젝트의 `church-media-onedrive` 비밀에 연결 정보 저장 완료 결과를 제공했다. 가져오기 도구는 복호화한 값을 gcloud stdin으로 전달하며 평문 파일을 만들지 않았다. 서버 전용 서비스 계정 권한, 클라우드 런타임의 실제 폴더 접근 검증, 자격 증명 쓰기 직렬화 및 파일/DB 매핑 적용은 남아 있다. Mac의 기존 연결은 유지한다.

2026-10-14 Google 실행 계정 준비: 사용자 출력으로 `media-runtime@church-media-511519.iam.gserviceaccount.com` 생성 및 OneDrive 비밀 하나의 accessor/version-adder 권한 설정 완료를 확인했다. 읽기 전용 `media_automation.cloud.onedrive_probe`는 실행 계정으로 비밀을 읽어 선택된 두 폴더 메타데이터만 확인하고, 토큰 갱신은 메모리에서만 처리한다. 비밀 버전/파일/DB는 쓰지 않는다. 시험 코드 테스트 14개 통과. 클라우드 SDK를 포함한 v2 묶음 빌드·업로드 및 실제 Google 작업 실행은 사용자 단계로 남아 있다.

2026-10-14 Google OneDrive 실행 검증: 사용자 로그의 `media-onedrive-probe-fbkk4`가 정상 종료했다. 시험 코드의 성공 조건은 Google 비밀 읽기와 원본/완료본 폴더 접근 모두 통과하는 것이다. 참조된 원본 48개 중 기존 매핑 40개를 확인하고, 누락 8개(악보 7개·금요 배경음원 1개)를 선택된 OneDrive 원본 폴더로 Mac에서 복사했다. 새 파일은 충돌 시 실패하는 업로드로 생성했고, 다운로드 SHA-256 대조 모두 통과했다. 기존 로컬 원본·DB는 유지했다.
곡 44개·원본 파일 ID 48개·곡/자료 관계 46개·첨부 27개·검수 3개·주보 설정 1개·완료본 보관 기록 4개를 복사할 SQL을 준비했다. 파일 ID의 실제 위치·크기를 확인했으며 비밀 값·임시 다운로드 URL은 SQL에서 제외했다. 원본/첨부 참조 모두 48개 파일 매핑에 포함된다. 실제 Supabase 목록 이관은 사용자 실행 단계로 남아 있으며 현재 8876 저장은 여전히 로컬 DB다. 클라우드 웹 공개 배포와 제작 작업 연결은 아직이다.
