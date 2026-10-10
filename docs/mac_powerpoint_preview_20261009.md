# macOS PowerPoint PPTX 미리보기 — 2026-10-09

## 사용자 기능

- **새 제작:** 제작한 PPTX/PDF는 다시 업로드하지 않습니다. 생성 완료 작업의 '6. 자동 검수 및 최종 확인'에서 산출물을 고르고 미리보기를 확인합니다.
- **기존 제작물 검수(선택):** 이미 만든 과거 PPTX/PDF를 별도 검수용 복사본으로 등록하는 기능입니다. 새 주간 제작에는 사용하지 않습니다.
- 두 화면 모두 PPTX는 사용자 요청에 따라 **맥 Microsoft PowerPoint 우선** 변환하고, 미설치 환경에서 LibreOffice가 있으면 사용합니다.
- PDF는 별도 변환 없이 브라우저에서 표시합니다.

## 안전 및 검수

- 변환 도구는 **별도 임시 복사본**만 엽니다. 원본 PPTX/PDF는 수정하지 않습니다.
- 변환된 PDF의 페이지 수가 원본 PPTX의 슬라이드 수와 다른 경우 성공으로 처리하지 않습니다.
- 결과 PDF는 검수 작업 또는 생성 작업의 별도 `preview/` 또는 `previews/` 폴더에 저장됩니다.
- 오디오, 영상, 애니메이션, 효과, 화면 잘림, 실제 교회 프로젝터 출력, 저작권/사용 허락은 PDF 변환이 확인해주지 않습니다.
- **macOS 자동화 권한**에서 터미널/파이썬이 PowerPoint를 제어할 수 있어야 합니다. 처음 실행 시 권한 요청이 나타날 수 있습니다.
- PowerPoint가 예배 제작 작업을 수행 중이면 생성 작업의 미리보기는 새로 변환하지 않습니다. 아직 외부 CLI까지 포괄하는 전역 잠금은 완성되지 않았으므로 실제 예배 제작 중에는 미리보기를 실행하지 마세요.
- 변환 실패 시 원본은 변하지 않으며, 검수 상태를 임의로 완료 처리하지 않습니다.
- 동일 원본에 대한 과거 LibreOffice 캐시는 자동 대체하지 않습니다. PowerPoint 결과로 다시 확인하려면 별도 검수 작업을 등록합니다.

## Mac에 선택 반영

기준: `feature/existing-qa-preview-20261009` 코드에 추가하는 변경입니다. 기존 맥의 9/27 자료는 그대로 둡니다.

```bash
git fetch origin feature/mac-powerpoint-preview-20261009
git restore --source=origin/feature/mac-powerpoint-preview-20261009 -- \
  src/media_automation/web/pptx_preview.py \
  src/media_automation/web/job_previews.py \
  src/media_automation/web/existing_inspections.py \
  src/media_automation/web/application.py \
  src/media_automation/web/server.py \
  src/media_automation/web/static/index.html \
  src/media_automation/web/static/app.js \
  tests/test_web_pptx_preview.py \
  docs/mac_powerpoint_preview_20261009.md
python -m pytest -q tests/test_web_pptx_preview.py
python -m pytest -q
```

그 뒤 실행 중인 `webapp.py`를 Ctrl+C로 종료하고 다시 시작한 후 다음을 확인합니다.
1. 새로운 제작 완료 작업에서 PPTX가 목록에 자동 연결되는지.
2. 기존 제작물에서 PPTX 업로드 후 '미리보기 준비'가 작동하는지.
3. 맥 자동화 권한 요청과 PDF 페이지 수가 실제 PPTX 슬라이드 수와 일치하는지.
4. PowerPoint로 원본 PPTX를 직접 열어 PDF와 실제 화면을 비교하는지.

## 테스트 상태

작성 환경에서 실제 macOS PowerPoint를 실행하지 못했으므로 **맥 실제 변환 검증은 아직 하지 않았습니다.** 단위 테스트는 앱 호출을 흉내 내는 모의 실행만 다룹니다. 검증 완료라고 단정하지 않습니다.
