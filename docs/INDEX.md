# 미디어 자동화 프로젝트 문서 길잡이

> 문서에 적힌 검수/배포 상태는 **작성 당시의 상태**다. 새 기능 완료·운영 전환 여부는 가장 최근의 실제 실행 기록을 별도로 확인한다. 사용자의 주간 예배 수정 지시와 [AGENTS.md](../AGENTS.md)를 언제나 우선한다.

## 어디부터 보면 되나?

| 질문 | 먼저 볼 문서 | 용도 |
|---|---|---|
| 현재 실행 파일과 폴더가 왜 여러 개인가? | [저장소 폴더 구조](repository_layout_20261022.md) | 현재 앱, 과거 스냅샷, 복구 실행기, 보호할 원본 구분 |
| `scripts/`의 명령어 중 무엇을 사용하고 주의해야 하나? | [스크립트 사용 안내](../scripts/README.md) | 자동 관계 분류, 수요·주일 악보 검사 공통화, 민감한 수동 도구 |
| Mac·Windows 실제 작업 폴더를 어떻게 보존하나? | [Windows 인수인계](windows_review_handoff_20261022.md) · [로컬 통합 기준](local_consolidation_20261013.md) | DB 덮어쓰기·강제 reset·무단 정리 금지 |
| 검수용 UI 자동 배포는 어떻게 연결됐나? | [UI 미리보기 자동 갱신](ui_preview_auto_sync_20261022.md) · [WIF 설정 기록](github_ui_preview_wif_setup_20261022.md) | 운영 Cloud Run과 별도 |
| 코드만으로 실패·중복·동시수정을 어디까지 검증했나? | [오프라인 제작 안전 검수](offline_production_safety_gate_20261022.md) | 가짜 계정/전송, **실제 원격 연동 아님** |
| 실제 출력 엔진은 시험했나? | [합성 파일 실제 렌더링 기록](offline_real_rendering_20261022.md) | 실제 엔진 사용, 실제 교회 원본·본문 검수 아님 |
| 진짜 공동 운영 전에 무엇이 필요한가? | [독립 스테이징 설계](isolated_live_staging_plan_20261022.md) | 테스트 Supabase/OneDrive/GCP와 운영 분리 |
| 현재 운영 웹/Job 버전과 복구 방법은? | [운영 배포·복구 runbook](production_release_rollback_runbook_20261022.md) | 조회 전용 점검, 무승인 업데이트 금지 |
| 2026-10-14 실제 Cloud Run 작업은 무엇을 검증했나? | [당시 실측 기록](hosted_runtime_20261014.md) | 이후 UI 브랜치와는 버전 차이 |
| 수요·금요·주일별 원칙은? | [수요](wednesday_workflow.md) · [금요 Zoom](friday_zoom_workflow.md) · [주간 입력 상태](weekly-data-schema.md) | 한 주의 최신 지시를 우선 |

## 작업 구분

- **현재 프로그램**: `src/media_automation/` 중 `_legacy_migration/`을 제외한 모듈, 루트의 CLI와 `scripts/` 단일 기능 도구.
- **과거 비교·복구용 코드**: `experiments/`, `src/media_automation/_legacy_migration/`, `scripts/archive/`. 파일명이 비슷하더라도 삭제하지 않는다.
- **읽기 전용 교회 자료**: `sources/`, 비공개 주간 입력·성경·악보·영상·DB. GitHub 체크아웃에 자동 포함된다고 가정하지 않는다.
- **자동 CI**: `.github/workflows/repository-hygiene.yml`(구조/CLI), `offline-production-safety.yml`(가짜 저장·전송), `offline-real-rendering.yml`(합성 출력), `ui-preview-sync.yml`(별도 비공개 UI 미리보기).

이전 날짜의 문서는 감사 기록으로 계속 보존한다. README 최신 안내와 실제 CI 실행 기록이 서로 다르면, 성공/실패를 단정하지 말고 해당 빌드의 원본 SHA·실행 결과를 확인한다.
