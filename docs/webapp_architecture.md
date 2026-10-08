# 웹앱 구조 확정 — 2026-10-09

## 범위와 현재 구현

기존 맥 제작기를 유지하고 브라우저 → 로컬 API → 공통 작업 서비스 → 예배별 CLI → 결과 파일 순서로 연결했다.
현재 구현은 신뢰된 자료를 다루는 맥 1대·운영자 1명용 실행 가능한 기반이다.
공용 서비스 완성 또는 전체 제작물 검수 완료라는 의미는 아니다. 외부 배포는 하지 않았다.
프런트는 별도 빌드 없는 HTML/CSS/JS, API는 Python 표준 라이브러리로 구성하여 기존 Python 환경에 추가 의존성을 만들지 않았다.

## 코드 책임

| 위치 | 책임 |
|---|---|
| webapp.py | 로컬 실행 진입점 |
| src/media_automation/web/static/ | 작업 생성·자료 등록·상태·다운로드 화면 |
| src/media_automation/web/server.py | HTTP, 로컬 토큰, 업로드 크기, 응답, 다운로드 경계 |
| src/media_automation/web/application.py | 작업 목록·등록·직렬 실행·중단 복구 |
| src/media_automation/production/jobs.py | 작업별 워크스페이스, 기존 CLI 실행, 로그, 신규 산출물 판정 |
| sunday.py / wednesday.py / friday.py / bulletin.py | 기존 예배별 제작 흐름 |
| src/media_automation/weekly_data/ | 공통 데이터 및 UNSET/NONE/VALUE |
| src/media_automation/bulletin/ | 전달 주보 해석·교차검수·인쇄 PDF |
| assets/bulletin/ | 사용자가 확정한 디자인 자산 |
| tests/test_web_application.py | 실제 HTTP·인증·경로·상태·산출물 노출 검증 |

## 저장 구조

기본 저장소: ~/Library/Application Support/media-automation/jobs/<job_id>/
- job.json: 서비스·날짜·생성시각·상태·시도 횟수·결과 목록·종료코드
- workspace/: 작업의 코드 스냅샷 및 명시적으로 등록한 입력
- workspace/input/: 해당 주 원본·주보 전달 파일
- workspace/data/: 명시적으로 등록한 성경 등 데이터
- workspace/output/: 해당 작업의 입력 파생 데이터 및 생성 결과
- attempt-N.log: 로컬 진단 로그
- running.lock: 동일 작업 중복 실행 방지

새 작업에는 코드와 확정 디자인 자산만 복사한다. 이전 주 입력, 결과, 악보, 성경 사본은 자동 복사하지 않는다.
교회 찬양 라이브러리의 영구 저장 위치는 여전히 미확정이다. 위 작업 저장소는 찬양 라이브러리가 아니다.
입력 수정은 새 파일 경로나 새 작업으로 처리한다. 기존 파일 덮어쓰기는 차단한다.
추가 입력을 등록하면 결과 목록을 무효화하고 needs_input으로 되돌린다.

## 상태 계약

needs_input → queued → running → generated / failed
서버 재시작 시 queued/running → interrupted, 자동 재실행하지 않는다.
interrupted 작업은 새 작업으로 등록한다. 남은 맥 제작 프로세스가 종료됐는지 먼저 확인한다.
웹 계층은 전체 작업 중 1개만 실행하여 PowerPoint 자동화 충돌을 줄인다.
CLI 직접 호출 등 다른 프로세스와의 전역 잠금은 아직 없다.
generated는 종료코드 0 + 새로 생성되거나 변경된 PDF/PPTX를 의미한다.
시각검수·실물 인쇄·미디어 재생·사용 허락 상태는 생성 상태와 별도 축이다.
현재 자동/수동 검수 기록 API는 미구현이며 문서로 기록한다. 미검수를 합격 처리하지 않는다.

## API v1 (로컬)

모든 API 요청: Authorization: Bearer <실행마다 생성된 토큰>
- GET /api/jobs: 목록
- POST /api/jobs: {service, date}, 201
- GET /api/jobs/<id>: 상태·등록 자료·산출물
- POST /api/jobs/<id>/files?path=<상대경로>: 파일 바이트, 201
- POST /api/jobs/<id>/run: {source?: 원본 PPTX 상대경로}, 202
- GET /api/jobs/<id>/artifact?path=<산출물 상대경로>: generated의 허용 목록 파일만

서비스: bulletin, sunday, wednesday, friday. friday는 현재 Zoom CLI이며 대면 날짜를 추정하지 않는다.
업로드 최대 128MiB/파일. .yaml/.yml/.json/.txt/.hwp/.ppt/.pptx/.pdf/.png/.jpg/.jpeg/.mp3/.mp4/.ttf.
output에는 YAML/JSON 입력만 허용한다. 이전 PDF/PPTX를 새 결과로 등록할 수 없다.
잘못된 입력 400, 인증 누락 401, 외부 Host/Origin 403, 없는 경로 404.
토큰은 URL fragment로 첫 접속에만 전달하고 브라우저 세션에 보관한다. API 인증에는 헤더를 사용한다.
127.0.0.1에만 바인딩한다. 폴더 분리는 보안 샌드박스가 아니므로 공개 서버로 노출하지 않는다.

## 입력 화면의 후속 연결 계약

현재는 상대 경로를 직접 등록하는 개발용 흐름이다. 다음 작업은 아래 입력 유형을 선택하면 경로가 자동 결정되게 하는 것이다.
- 주일: 해당 주 안내 / 전달 주보 / 원본 PPTX / 검수 악보 / 개역개정 데이터
- 주보: 전달 주보 / 같은 주 주일 공통 데이터 / 호수와 표어 등 확정 입력
- 수요: 해당 주 안내 / 기존 수요 원본 / 검수 악보 / 개역개정 데이터
- 금요 Zoom: 해당 주 안내 / Zoom 원본 / 명시 선정 영상·음원 / 개역개정 데이터

파일 존재는 의미 검증 완료가 아니다. 입력 확인 단계는 날짜·서비스·필수 항목·최신 지시 출처·명시적 없음 상태를 보여줘야 한다.
주일/PPT와 주보의 공통 필드는 단일 주간 데이터에서 공유한다. 질문은 원문 4개를 유지한다.
값 구조는 기존 WeeklyDataState 모델을 재사용한다. 출처·수정 이력·확정시각은 향후 별도 레코드로 연결한다.

## 실행

```bash
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python webapp.py
```
표시되는 접속 링크를 같은 맥 브라우저에서 연다. 종료 Ctrl+C.
`--repository`, `--storage`, `--port`로 코드·작업 폴더·포트 지정 가능.
설치형 패키지에도 static 파일이 포함되도록 package-data를 선언했다.
실제 PPT 제작은 맥 PowerPoint와 예배별 외부 자료가 필요하다. 일반 채팅 환경에서는 이를 대신 검수했다고 말하지 않는다.

## 다음 구현 순서와 완료 기준

1. 입력 유형별 폼·최신 지시 누적·필수자료 점검. 경로 직접 입력 없이 같은 주 데이터 준비, UNSET 차단.
2. 공통 데이터 편집·PPT/주보 교차검수. 호수·본문·제목·담당자·찬양·질문·광고·일정 차이 설명.
3. 검수 파이프라인 연결. PDF 두 인쇄면/PPT 전장 미리보기, 자동 QA, 사람이 확인한 상태와 증거 별도 저장.
4. 작업 실행 관리 강화. 하위 프로세스 트리 종료·취소·전역 맥 워커 잠금·재시작 내구성·보관 정책.
5. 실제 환경 인수검수. 주보 실제 양면 인쇄, 금요 실제 영상·음원 재생, 각 예배 안내→제작→검수 반복.
6. 공용 배포. 사용자·역할·접근제어·업로드 내용/경로 검사·개인정보/로그 처리·백업·모니터링을 완료한 뒤 별도 호스팅 연결.

도메인 media.hjbbc.or.kr 방향은 과거 결정 기록에 있다. 실제 등록·호스팅·외부 공개는 수행하지 않았다.
