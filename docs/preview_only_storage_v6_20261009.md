# 미디어 제작실 미리보기 단순화 + 임시 캐시 보관 v6 (2026-10-09)

## 사용자 결정

- **웹 화면은 미리보기 중심**. 검수자, 체크리스트 드롭다운, 검수 메모, JSON 보고서 버튼을 숨기고 해당 화면에서 자동 실행하지 않는다.
- 자동 구조 QA 모듈과 기존 기록 API는 하위 호환을 위해 보존하지만 웹의 일반 사용자 흐름에서는 호출하지 않는다.
- 새 제작 결과(PPTX/PDF)는 추가 업로드 없이 미리보기.
- 이미 만들어 둔 파일은 **'기존 PPT·PDF 미리보기(선택)'**에서만 파일을 선택한다. 이 업로드는 이번 주 예배 제작 입력으로 절대 사용하지 않는다.
- PPTX는 맥 PowerPoint 우선 PDF로 변환하고, 없을 때 LibreOffice 시도. 원본 변경 금지.
- **확정 주보 디자인과 예배별 PPT 형식을 수정하지 않는다.**

## 실제 로컬 보관의 경계

1. 생성 작업 작업공간: `~/Library/Application Support/media-automation/jobs/<job-id>/workspace/`
   - 제작 엔진은 작업별 코드 스냅샷과 자산, 입력, 생성된 PPTX/PDF를 보관한다.
   - **완성된 PPTX/PDF와 제작 입력은 자동 삭제하지 않는다.** 다운로드를 잊으면 데이터가 사라지므로, 이후 미디어팀과 보관 기간을 확정해야 한다.
2. 기존 파일 미리보기 사본: `jobs/_existing_inspections/<id>/source.pptx` 또는 `.pdf`
   - **새로 업로드한 미리보기 전용 사본**에는 `preview_only=true`, `expires_at`을 명시한다.
   - 24시간 지나면 다음 앱 접근/조회/등록 때 해당 사본 및 파생 PDF가 정리된다.
   - 임시 업로드 원본 사본의 합계 512MiB를 넘는 등록은 차단한다. 
   - **과거 v5에 저장된 검수 기록(미리보기 전용 표시가 없는 폴더)은 자동 삭제하지 않는다.** 필요한 파일을 잘못 지우지 않기 위해서다.
3. 새 제작 미리보기 PDF: `jobs/<job-id>/previews/<hash>/slides.pdf`
   - 변환 미리보기의 캐시 수명 24시간. 다음 해당 미리보기 조회 때 만료 파일을 정리한 뒤 새로 만들 수 있다.
   - **원본 PPTX와 작업의 산출물 목록은 그대로 유지한다.**

**중요:** 로컬 저장만으로 별도 클라우드 요금이 자동 발생하지는 않으나, 언젠가 서버에 배포하면 저장소 운영 비용이 생길 수 있다. 소스 코드 GitHub push가 주간 PPT/YAML/영상의 원격 보관을 의미하지 않는다.

## 검증 명령

```bash
python -m pytest -q tests/test_web_preview_only.py
python -m pytest -q tests/test_web_pptx_preview.py
python -m pytest -q
```

테스트가 통과하면 기존 `python webapp.py`를 종료(Ctrl+C)하고 재시작한다. UI에서 '기존 PPT·PDF 미리보기(선택)'과 '6. 제작 결과 미리보기'가 표시되고 사람 검수 입력창이 사라졌는지 확인한다.

**검증 상태:** 코드 저장 완료. 작성 세션에서 Mac PowerPoint를 실제 실행한 테스트 및 로컬 pytest는 수행하지 못했다. 사용자의 맥 검증 결과가 필요하다.

## 적용 범위

기반: `feature/mac-powerpoint-preview-20261009`.
해당 브랜치의 아래 파일만 맥에 선택 적용해야 하며, 브랜치 전체 병합은 피한다.

- src/media_automation/web/static/index.html
- src/media_automation/web/static/app.js
- src/media_automation/web/static/style.css
- src/media_automation/web/existing_inspections.py
- src/media_automation/web/job_previews.py
- tests/test_web_preview_only.py
- docs/preview_only_storage_v6_20261009.md

`sources/`, `input/`, `output/`, 주간 YAML/PPT 원본은 수정 대상이 아니다.
