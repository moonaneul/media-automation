# 웹 입력 화면 간소화 및 기록 없는 기존 파일 미리보기 (2026-10-09)

## 사용자 결정

1. 새 제작이 메인. 새 제작 → 현재 작업 상세 → (접힌) 이전 작업 이어하기 → 기존 파일 보기(선택)로 배치.
2. 제작 목록은 **작업이 중단되거나 브라우저를 다시 열었을 때 이어서 작업·다운로드하기 위한 것**이므로 삭제하지 않고, 접힌 '이전 작업 이어하기'로 제공.
3. 기존 제작 파일 미리보기는 **파일 선택 → 미리보기** 한 번의 동작. 예배 종류·원본 날짜·검수 이력·검수자·확인 기록을 만들지 않음.
4. 제작 전 확인은 항목별 상태를 텍스트와 차분한 색으로 함께 표시.
   - VALUE → 입력됨 (내용 정확성까지 확인된 것은 아님)
   - NONE → 이번 주 없음
   - UNSET → 미제공
   - 파일 존재는 '등록됨', 확인할 오류는 '확인 필요'로 따로 표시.
5. 기존 주보 디자인, 주간 YAML/PPT, sources/는 변경 없음.

## 기술·보존 경계

- 새 `POST /api/preview-once?filename=...`는 Authorization과 Origin 검증 뒤 단일 파일을 받아 **PDF를 즉시 반환**.
- PDF는 유효성 확인 뒤 그대로 반환. PPTX는 로컬 임시 폴더의 복사본에서 기존 Mac PowerPoint/LibreOffice 변환기를 호출하고 응답 후 임시 폴더를 삭제.
- **새 미리보기용 기존 파일은 서버 작업 저장소에 업로드 복사본, 메타데이터, 기록 목록을 생성하지 않음.** 브라우저의 blob URL은 화면을 바꾸면 해제됨.
- 이전 버전 v5/v6에서 이미 저장한 자료까지 소급 삭제하지 않음. 서버 시작 때 `preview_only=true`로 분류되고 24시간이 지난 임시 복사본만 정리.
- 새 제작의 작업 입력과 PPT/PDF 최종 결과는 데이터 유실을 막기 위해 계속 로컬 보관. 사용자가 요청하지 않은 자동 클라우드 업로드·자동 삭제는 없음.
- 기존 검수 엔진과 레거시 기록 모듈은 호환성·기존 테스트를 위해 내부에 남지만 일반 화면과 기존 파일 업로드 API에서는 제외.
- PPTX PDF 변환은 음악·애니메이션·사용 허락 검증을 대신하지 않음.

## 코드

- `src/media_automation/web/preview_once.py`: 임시 파일 기반 변환, 동시 PPTX 변환 제한
- `src/media_automation/web/server.py`: 새로운 인증된 일회성 PDF 스트리밍 endpoint, 기존 파일 저장 endpoint 제거
- `src/media_automation/web/application.py`: 만료된 기존 v6 미리보기 사본 정리
- `src/media_automation/web/static/index.html`, `app.js`, `style.css`: 화면 순서·상태 시각화·기존 파일 기록 미생성
- `tests/test_web_preview_once.py`: 인증·비보관·임시파일 삭제·유효성·상태 구분
- `tests/test_web_preview_only.py`: 이전 UI 기대 조건을 현행으로 갱신

## 맥 적용 및 검증

```bash
cd ~/Documents/media-automation
git fetch origin feature/preview-ux-once-20261009
git restore --source=origin/feature/preview-ux-once-20261009 -- \
  src/media_automation/web/application.py \
  src/media_automation/web/server.py \
  src/media_automation/web/preview_once.py \
  src/media_automation/web/static/index.html \
  src/media_automation/web/static/app.js \
  src/media_automation/web/static/style.css \
  tests/test_web_preview_once.py \
  tests/test_web_preview_only.py \
  docs/web_preview_ux_v7_20261009.md
python -m pytest -q tests/test_web_preview_once.py tests/test_web_preview_only.py
python -m pytest -q
```

테스트가 통과하면 기존 웹 서버를 Ctrl+C로 끄고 `python webapp.py`로 재시작. 이전 작업 메뉴는 기본적으로 접혀 있고, 기존 파일을 미리보기로 열었을 때 목록에 추가되지 않아야 합니다.

## 검증 한계

JavaScript 구문 확인 및 HTML id 참조 검사 완료. **Python pytest 및 실제 Mac PowerPoint 변환은 이 작성 환경에서 실행되지 못함**. 맥 테스트가 통과하기 전에는 완료 검증이라고 하지 않습니다.
