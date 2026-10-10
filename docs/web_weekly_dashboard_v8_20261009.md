# 주간 수·금·일 제작 현황과 빠른 바로가기 (v8, 2026-10-09)

## 동작

- 화면 맨 위에 **주간 제작 현황**을 배치한다. 월요일~일요일 단위로 이전 주 / 이번 주 / 다음 주 전환 가능.
- **수요예배(수), 금요기도회 Zoom(금), 주일예배 PPT 및 주보(일)**의 기존 작업을 날짜와 유형으로 연결.
- 아직 만들지 않았다면 '아직 작업 없음' + '새 작업 준비' (종류/날짜만 미리 채우고 사용자가 '작업 만들기'를 눌러 확정).
- 작업이 있으면 '작업 열기'로 바로 상세 및 생성 산출물에 접근.
- 같은 날짜에 작업을 여러 개 만들면 모든 작업을 각각 펼쳐서 열 수 있으며 최신 등록 작업을 기본 표시한다. **최근 등록 = 최종 승인**으로 판단하지 않는다.
- 표시 상태: 자료 준비 중, 제작 대기, 제작 중, 제작 파일 있음·최종 검수 별도, 제작 실패, 중단됨·새 작업 필요.
- 별도의 주간 현황 저장 파일을 만들지 않고 ProductionJobs의 기존 `job.json`을 읽어서 구성.
- 화면의 '이전 작업 이어하기'는 다른 주차 또는 날짜가 잘못 등록된 작업도 찾을 수 있도록 보존.

## 제한

- 웹에서 생성되었거나 등록된 **이 맥의 로컬 작업만** 조회 가능. 로컬 HTTP 서버는 127.0.0.1로 묶여 있고 타인의 다른 컴퓨터에서 볼 수 없음.
- 다른 미디어팀원이 자기 컴퓨터에서 접속하려면 공유 서버, 사용자 인증, 공용 파일 저장소, 접근 권한, 백업과 보존 정책을 별도로 구현·배포해야 함. 이번 변경은 원격 공유를 구현하지 않음.
- 기존 generated 작업의 파일은 현재 웹에서 다운로드/미리보기 가능하지만, **완성본을 그대로 덮어쓰는 수정 기능은 제공하지 않음**. 수정본은 같은 날짜의 별도 작업으로 보존해야 하며, 기존 작업에서 동일 주차 자료를 재사용할 것인지는 명시적 지시 및 충돌 검증이 필요함.
- 금요 **대면 제작**은 구현 전이므로 현 카드의 금요는 Zoom. 대면 날짜를 자동 추정하지 않음.
- 이전 주의 담당자·찬양·성경·기도·주보 호수 등을 자동 승계하지 않는다.
- 제작 파일이 존재함을 최종 검수, 사용 허락, 실제 재생 완료로 표시하지 않음.

## 추가 파일/수정

- `src/media_automation/web/weekly_board.py`: 주차별 작업의 읽기 전용 정리.
- `src/media_automation/web/application.py`: 주간 정보 조회 메서드.
- `src/media_automation/web/server.py`: 인증된 `GET /api/weekly-board?date=YYYY-MM-DD`.
- `src/media_automation/web/static/index.html`, `app.js`, `style.css`: 카드·주차 탐색·바로가기.
- `tests/test_web_weekly_board.py`: 주차 경계, 단일/복수 작업, 없는 주, HTTP 인증과 무부작용 검사.

## 맥 적용 및 테스트

```bash
cd ~/Documents/media-automation
git fetch origin feature/weekly-status-dashboard-v8-20261009
git restore --source=origin/feature/weekly-status-dashboard-v8-20261009 -- \
  src/media_automation/web/weekly_board.py \
  src/media_automation/web/application.py \
  src/media_automation/web/server.py \
  src/media_automation/web/static/index.html \
  src/media_automation/web/static/app.js \
  src/media_automation/web/static/style.css \
  tests/test_web_weekly_board.py \
  docs/web_weekly_dashboard_v8_20261009.md

python -m pytest -q tests/test_web_weekly_board.py
python -m pytest -q
```

기존 웹 서버는 Ctrl+C로 종료하고 `python webapp.py`로 다시 실행한다. 주간 카드와 바로가기가 표시되는지 확인한다.

**검증 단계 구분**: 코드 작성과 JS 문법·요소 검사는 가능. 이 개발 세션에서는 사용자의 맥 로컬 작업에 접근할 수 없으므로 macOS 브라우저 실사용/pytest는 사용자가 실행한 결과로 확인해야 한다.
