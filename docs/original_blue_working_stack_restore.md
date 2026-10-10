# 원본 파란 웹앱 복구: 전체 스택 테스트

## 무엇을 복구했는가
`src/media_automation/_legacy_migration/ui/index.html`의 원본 화면과, 원본
`_legacy_migration/backend/server.py`의 다음 엔드포인트를 같은 서버에서 제공합니다.

- `/api/mode`, `/api/work`: 예배 내용 조회/저장 및 revision 충돌 처리.
- `/api/notice-file`: HWP5 텍스트 추출. 8MiB/20초 제한. 원본 파일 불변.
- `/api/songs`, `/api/attachments`, `/api/asset-review`: 원본 찬양·첨부·검수 계약.
- `/api/bulletin-settings`: 원본 주보 기본 설정 계약.
- 기타 원본 엔드포인트 코드는 유지했지만 제작/미리보기는 미검증.

**단순화했던** `/blue`, `/blue-original` 시험판을 메인 화면으로
교체하지 않습니다. 공식 웹앱 포트 8765도 변경하지 않습니다.
원래 JS의 예배별 입력 폼과 안내 해석기를 임의로 새로 작성하지 않습니다.

## 왜 별도 실행인가
원래 웹의 HTML/JS만 복사해 공식 웹앱 서버에 연결하면, HTTP 계약이 달라
HWP 첨부·저장·찬양 자료 관리가 끊깁니다. 원래 서버를 별도로 복구한 뒤
원본 동작을 입증하고, 그다음 공식 제작 API와 단계적으로 연결합니다.

## Mac에서 시험하기 (프로젝트의 기존 미커밋 수정 보존)
```bash
cd ~/Documents/media-automation

git fetch origin feature/working-original-blue-stack-20261010

git worktree add --detach \
  ~/Documents/media-automation-original-working \
  origin/feature/working-original-blue-stack-20261010

ROOT="$HOME/Documents/media-automation"
ORIG="$HOME/Documents/media-automation-original-working"
cd "$ORIG"

"$ROOT/.venv/bin/python" -m pytest -q \
  tests/test_original_blue_stack.py \
  tests/test_original_blue_bulletin_parser.py

"$ROOT/.venv/bin/python" scripts/run_original_blue.py --port 18767
```

브라우저: `http://127.0.0.1:18767/`.
원본 화면의 '안내문 입력'에서 HWP 첨부 → '포맷 채우기' →
'선택 항목 반영'을 시험합니다.

별도 테스트 저장 파일:
`~/Documents/media-automation-integration/original-blue-working/work.sqlite`

이 **별도 포트와 DB**에서는 기존 8767 시험판의 입력 자료, 혹은
원래 사용하던 다른 포트의 브라우저 localStorage 자료가 자동 복원되지 않습니다.
어느 쪽도 삭제하거나 덮어쓰지 않습니다. 기존 서버를 종료할 필요도 없습니다.

## 주보 10/11에 대한 입력 범위
원문에 있는 오후예배, 찬송가 목록, 교회 소식, 사역 일정,
목장 본문·제목·질문은 읽을 수 있습니다.
HWP5 표의 병합된 셀은 평면 텍스트 추출 시 행/열 연결이 손실될 수 있으므로
이번 주/다음 주 섬김은 실제 HWP 표를 확인해야 합니다.
'인도자'는 해당 표 셀의 **원문**이며 이름을 임의로 정해서는 안 됩니다.

`찬양: 79, 337, 382장`은 주보 목록이지 시작 찬양 1·2·3,
별도 찬송 등의 역할이 지정된 정보는 아닙니다.
`목장 본문: 단 1:8~9`도 주일 설교 본문과 항상 동일하다고
가정하지 않습니다.

## 아직 복구 완료로 볼 수 없는 범위
- 구버전 원본 PPT/PDF 엔진은 시스템별 런타임 경로와 누락된 템플릿에 의존합니다.
  예배용 PPT/PDF 정상 생성은 현재 검증하거나 보장하지 않습니다.
- HWPX는 현 저장소의 성경/주보 HWP 추출기가 아직 처리하지 못합니다.
- 원본 브라우저 화면의 실제 작동 및 영상/음원 재생은 Mac에서 확인 전입니다.
- 입력 통합/자료 이전은 하지 않았습니다. 사용자가 확인한 자료만 차후 이전해야 합니다.
- 테스트를 목적으로 Github에 HWP 원본 파일을 올리지 않습니다.

## 완료 판정 기준
원본 UI · 안내 추출 · 항목별 적용 · 서버 저장 · 재조회 · 수정 충돌
· 찬양/원본 관리가 정상 동작하는 것을 Mac에서 확인한 뒤,
복구 완료라고 부릅니다. 이후에만 원본 서버와 공식 PPT 엔진을 통합합니다.
