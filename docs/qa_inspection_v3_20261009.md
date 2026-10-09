# 3차 자동 검수: 독립 구조 점검 (초기 버전)

이 기능은 읽기 전용이고 결과는 별도의 JSON 파일로 저장합니다. 기존 PPTX/PDF와 sources/, 주간 입력 데이터는 변경하지 않습니다.

## 로컬 검증

```bash
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_qa_inspection.py
python -m pytest -q
python -m media_automation.qa output/sunday/sample.pptx --service sunday --reference '삼상 17:41~49' --report output/qa/sample.json
python -m media_automation.qa output/bulletin/sample.pdf --service bulletin --report output/qa/bulletin.json
```

예시 경로는 실제 생성된 파일의 경로로 변경합니다. 검사 대상 파일이 없으면 실행하지 않습니다. 오류가 발견되면 CLI 종료 상태 1, 구조상 오류가 없으면 0입니다. 검토 필요 사항은 구조상 오류가 없어도 보고서에 남습니다.

## 자동 확인 범위

- PPTX 열기, 슬라이드 개수, 텍스트의 '세례' 표기, 보이는 URL 및 외부 링크, 내장 미디어 관계 수
- 범위를 명시적으로 제공하면 텍스트에서 찾은 절 번호의 누락·중복과 수요·주일 다중 절 화면 주의
- 주보 PDF의 페이지 수 2, 각 페이지 A4 가로 방향
- JSON의 error/review 개수와 렌더링·재생·사용 허락 미확인 상태

## 의도적으로 검증 완료라고 표시하지 않는 항목

- PPT/주보 실제 렌더링, 이미지 내부 성경 텍스트, 악보 잘림
- 개역개정 구절 원문과의 교차검증(사용 허가된 원문 데이터 연결 필요)
- 전체 순서의 빈 슬라이드/찬양곡 정확성(블록 메타데이터 연결 필요)
- 금요 미디어 실제 재생, 저작권·사용 허락 확인
- 주보 논리 쪽 [4|1], [2|3] 실제 배치 및 물리 출력·접지

이 초기 모듈은 기존 웹에서 아직 호출하지 않습니다. 입력 방식을 결정하기 전에도 독립 사용 가능하며, 후속 단계에서 ProductionJobs 및 웹 검수 기록과 연동합니다.

주의: 사용자 맥에만 있는 1차·2차 웹 입력 변경은 이 원격 기능 브랜치의 기반에 포함되어 있지 않을 수 있습니다. **기능 브랜치를 원본에 통째로 병합하지 말고, QA 전용 파일과 pyproject.toml 의존성 변경만 선택 반영**해야 합니다.
