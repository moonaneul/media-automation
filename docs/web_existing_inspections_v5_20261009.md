# 기존 제작물 검수 + 미리보기 v5

## 목적

새 주간 제작과 독립적으로 **기존 PPTX·주보 PDF 파일을 선택**하여 별도 검수 작업에서 읽기 전용 복사본을 검사합니다. 이전 파일을 새로운 예배 날짜나 입력으로 자동 승계하지 않습니다. 원본 파일을 덮어쓰지 않습니다.

## 화면

'기존 제작물 검수'에서 예배 종류, 기존 파일의 실제 날짜, PPTX 또는 PDF를 선택합니다. 등록 후 자동 검사, 사람 확인 기록, JSON 보고서 다운로드, PDF 화면 미리보기를 사용합니다. 금요 대면은 이 **검수 선택지**로만 존재하며 자동 제작 지원을 의미하지 않습니다.

## 안전

- 별도 위치: `~/Library/Application Support/media-automation/jobs/_existing_inspections/<id>/`
- 원본 복사본 `source.pptx` 또는 `source.pdf`, SHA-256, 검수 JSON은 각각 별도 파일.
- 기존 ProductionJobs 입력/산출물 allowlist와 혼합하지 않습니다.
- 허용: PPTX(수요·주일·금요), PDF(주보). 업로드 용량 128MiB 이하.
- QA 기록은 복사본 해시와 연동되어 파일 변경 시 무효화됩니다.
- 자동 구조 검사 완료는 실제 렌더링·악보 잘림·개역개정 대조·미디어 재생·저작권 확인 완료가 아닙니다.
- 기존 9/27 파일도 **사용자가 직접 선택하여 업로드할 때에만** 검사 대상으로 등록합니다.

## 미리보기 제한

- PDF는 업로드한 PDF의 검수용 사본을 그대로 브라우저의 PDF 표시 기능으로 봅니다.
- PPTX는 명시적으로 '미리보기 준비'를 선택하고, `soffice`/LibreOffice가 시스템 PATH에 있는 경우 **별도 임시 복사본을 PDF로 변환**합니다.
- PPTX 변환 실패나 LibreOffice 미설치 시 **미리보기를 제공하지 않습니다**. 원본은 그대로 보존됩니다.
- PDF 변환 결과와 Microsoft PowerPoint의 실제 렌더링·애니메이션·음원 재생은 다를 수 있습니다.
- PDF 미리보기 표시가 된 것과 주보 실물 양면 인쇄·접지가 확인된 것은 별개입니다.

## 실행 검증

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_web_existing_inspections.py
python -m pytest -q
python webapp.py
```

기존 로컬 서버는 Ctrl+C 후 재시작해야 새로운 화면이 뜹니다.

**주의:** 원격 브랜치에 코드 작성까지만 완료했습니다. 작성 환경에서 Python 실행기가 작동하지 않아 테스트 통과는 아직 확인되지 않았습니다. 맥에서 테스트 및 브라우저 확인 후 검증 완료 여부를 판단합니다.

## 적용

원격 `feature/existing-qa-preview-20261009`에서 아래 파일만 선택 반영합니다.
- src/media_automation/web/existing_inspections.py
- src/media_automation/web/application.py
- src/media_automation/web/server.py
- src/media_automation/web/static/index.html
- src/media_automation/web/static/app.js
- src/media_automation/web/static/style.css
- tests/test_web_existing_inspections.py
- docs/web_existing_inspections_v5_20261009.md

수정된 원본/주간 입출력은 건드리지 않습니다.
