# 웹 검수 연동 v4 — 2026-10-09

## 변경 사항

로컬 미디어 제작실의 생성 완료 작업에 독립 QA 화면 및 API를 추가했습니다.
기존 제작 엔진, 주보 디자인, 주간 입력, sources/는 변경하지 않습니다.
입력 방식의 최종 결정, 금요 대면, 영상 자동 확보는 이 변경에 포함하지 않습니다.

- 산출물 목록에 **실제로 등록된 generated PPTX/PDF**만 검수 가능.
- 자동 QA는 기존 media_automation.qa.inspection.inspect_file() 재사용.
- 자동 보고서: 오류/error, 확인 필요/review, 개별 메시지, 슬라이드 번호.
- 사람 검수: 검수자, 항목별 pending/checked/issue, 메모, 검수 시각.
- SHA-256을 붙여 원본이 바뀌면 이전 보고서와 사람 검수 기록이 무효.
- 자동 검사를 다시 실행하면 사람 검수 기록은 초기화.
- 외부 사용 허락과 실제 재생은 자동 통과 표시 불가.
- 주보 PDF 출력·접지는 직접 확인해야 함.
- 입력·제작·검수 상태를 서로 분리하고, 완료 표시가 실제 사용 허락을 보증하지 않음.

## API

인증과 Origin 제한은 기존 웹 인증을 재사용합니다.

- GET /api/jobs/<id>/qa?path=<artifact>
- POST /api/jobs/<id>/qa/inspect : {path,reference?}
- POST /api/jobs/<id>/qa/confirm : {path,sha256,reviewer,note,checks}
- GET /api/jobs/<id>/qa/report?path=<artifact>

JSON 보고서는 작업 저장소의 <job_id>/qa/ 아래에 별도 보관합니다.
생성본의 워크스페이스나 원본은 수정하지 않습니다.
자동 보고서와 사람 검수 기록은 서로 다른 필드에 보존합니다.

## 검증

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_web_qa_review.py
python -m pytest -q
python webapp.py
```

로컬 웹에서 **생성 완료된 작업**을 열고 6. 자동 검수 및 최종 확인 섹션에서 검사/기록/다운로드를 확인합니다.
아직 실제 슬라이드 렌더링 미리보기와 개역개정 전문 대조, 주일·주보 전체 교차검수는 추가되지 않았습니다.

안전한 적용: 기존 feature/web-qa-v4-20261009 브랜치에 미커밋 9/27 자료가 있을 수 있으니 전면 병합이 아니라 아래 수정 대상만 선택 반영해야 합니다:
- src/media_automation/web/application.py
- src/media_automation/web/server.py
- src/media_automation/web/qa_review.py
- src/media_automation/web/static/app.js
- src/media_automation/web/static/index.html
- src/media_automation/web/static/style.css
- tests/test_web_qa_review.py
- docs/web_qa_review_v4_20261009.md

## 미검증 상태

원격 브랜치에 코드를 작성했으나 작성 환경의 Python 실행기 오류로 **로컬 자동 테스트 미실행**입니다.
사용자 맥에서 pytest 및 브라우저 실사용 검증을 통과하기 전에는 완료/배포 판정을 하지 않습니다.
