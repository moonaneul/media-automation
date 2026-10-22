# scripts/ 명령어 사용 안내 — 2026-10-22

이 폴더의 모든 스크립트를 실행하거나 삭제하지 않는다. 정식 사용 흐름과 옛날 복구 도구를 확인하기 위한 길잡이이다. 실제 제작과 원본 검수는 사용자 요청 전까지 진행하지 않는다.

## 공통 출발점

사용자가 일반적으로 직접 실행할 진입점은 **루트** `wednesday.py`, `friday.py`, `sunday.py`, `bulletin.py`, `webapp.py`다. `scripts/`의 여러 프로그램을 외워서 각각 실행하는 것을 기본 사용 방식으로 만들지 않는다.

| 목적 | 권장 출발점 | 실제 코드에서 확인한 일부 하위 도구 |
|---|---|---|
| 수요 주간 입력·수정 | `python wednesday.py --help` | `parse_wednesday_notice.py`, `resume_wednesday_week.py`, `resolve_wednesday_review.py`, `register_wednesday_song.py` |
| 금요 Zoom 주간 입력·수정 | `python friday.py --help` | `start_friday_zoom_week.py`, `resume_friday_zoom_week.py`, `resolve_friday_zoom_review.py` |
| 주일 주간 입력·수정 | `python sunday.py --help` | `parse_sunday_notice.py`, `resume_sunday_week.py`, `complete_sunday_week.py`, `register_sunday_song.py` |
| 주일 주보 단독 관리 | `python bulletin.py --help` | `bulletin.py`가 직접 처리 |
| 맥 로컬 웹 실행 | `start.command` → `scripts/start_primary.py` | 기존 실사용 DB·포트 8876 보존 |
| 기존 파란색 UI 복구 시험 | `scripts/run_original_blue.py` | `_legacy_migration/`의 복구 코드 참조, **공식 웹 서버 대체 금지** |

※ 표는 **실제 코드의 문자열 참조를 확인한 사례**이며, 매주 해당 스크립트가 실제 실행된다는 뜻은 아니다. 금요 대면 방식은 Zoom과 별개이므로 실제 사용 여부를 일괄 가정하지 않는다.

## 이번에 중복 처리만 통합한 부분

- `refresh_wednesday_song_checklist.py` 및 `refresh_sunday_song_checklist.py`의 정확한 예상 악보 파일명 검사 로직은 `src/media_automation/weekly_song_checklist.py`의 `refresh_exact_song_files()`를 사용한다.
- 수요·주일의 예배 정책·콘텐츠와 각 스크립트의 실행 옵션, READY/MISSING 메시지, 누락 시 종료코드 `2`는 유지한다.
- `expected_filename`에 맞는 파일만 확인하고, 비슷한 이름의 다른 악보·이전 주 자료를 임의 선택하지 않는다.
- 사용자가 명시적으로 등록한 첨부/선택 상태를 추정해 바꾸지 않는다. 파일 이름이 없는 항목을 임의로 새로 찾거나 생성하지 않는다.
- CLI 호환성은 [GitHub Actions #4](https://github.com/moonaneul/media-automation/actions/runs/39732522778) **31개 테스트 통과**로 확인했다.

## 나머지 스크립트의 상태를 자동 분류하는 방법

```bash
python scripts/audit_script_usage.py --check
python scripts/audit_script_usage.py --json
```

이 도구는 Git의 추적 파일만 읽고, 루트 명령어와 하위 스크립트에 적힌 **정적인 `*.py` 문자열 참조**를 따라가며 목록을 출력한다. 실제 Python 함수 호출을 실행하거나 네트워크에 접속하지 않는다. 발견한 관계를 다음 세 가지로 표시한다.

- `referenced_by_root_cli_chain`: 루트 명령어·간접 스크립트에서 문자열 참조가 확인됨
- `mentioned_in_github_workflow`: GitHub Actions workflow 문서에서 이름을 참조함
- `standalone_or_unresolved_static_reference`: 두 경로에서는 참조가 발견되지 않음. **사용하지 않는다, 삭제해도 된다는 의미가 절대로 아님**

2026-10-22 기준: 정식 `scripts/` Python 73개(이 중 루트 CLI 참조 31개, workflow 참조 8개, 별도 확인 36개), `scripts/archive/` Python 4개. 참조 두 유형은 서로 겹친다.

## 직접 실행 전에 주의할 도구

| 스크립트 | 주의할 이유 |
|---|---|
| `sync_workspace.py push` | `git add --all` 이후 커밋·푸시까지 수행하므로 미검토 파일이 있을 때 실행 금지 |
| `upload_missing_sources.py` | OneDrive 특정 폴더에 원본 파일을 업로드할 수 있음. 독립 시험 계정 미확보 상태에서는 실행 금지 |
| `import_onedrive_connection.py` | 암호화된 OneDrive 연결 상태를 바꿀 수 있음 |
| `export_onedrive_connection.py` | 민감한 연결 내보내기 자료가 생길 수 있음 |
| `export_supabase_works.py` | 실제 주간 입력 데이터를 외부 파일로 내보낼 수 있음 |
| `prepare_runtime_assets.py` | 비공개 런타임 자료를 작업 폴더에 준비할 수 있음 |
| `package_hosted_runtime.py` | 호스팅 런타임 배포를 위한 자산을 묶을 수 있음 |

위 표는 사전 주의 목록이지 다른 스크립트가 자동으로 안전하다는 증명이 아니다. 원본 삭제·덮어쓰기와 새 예배 결과 생성은 명시적으로 요청받기 전에는 하지 않는다.

기존 Windows 두 작업 폴더 사이에 누락된 원본만 안전하게 복사할 필요가 있으면 [단일 작업 폴더 전환 가이드](../docs/single_workspace_adoption_20261022.md)와 `scripts/prepare_single_workspace.py`를 참고한다. 명시적인 `--copy`가 없으면 **읽기 전용 예비 검사**만 수행한다. 기존 데이터·완성본을 삭제하거나 덮어쓰지 않는다.

## Mac·Windows에서 코드와 자료가 분리되어 있는지 확인

`python scripts/check_workspace_split.py`은 체크아웃의 현재 브랜치/커밋, 미커밋 코드 유무, Git의 비공개 파일 추적 여부, 로컬 DB 존재 여부 **만** 확인한다. `--json --compare`로 다른 기기의 안전 요약과 코드 버전을 비교할 수 있지만 DB 내용은 비교하지 않는다. 사용 절차는 [다중 기기 코드·데이터 관리](../docs/multi_device_workflow_20261022.md)를 따른다.

## 절대 자동 정리하지 않는 경로

- `sources/`: 제공된 교회 원본 — 읽기 전용
- `input/`: 주간 안내·악보·미디어 — 이전 입력을 새 주로 승계하지 않음
- `output/`: 실사용 DB·검수 상태·완성본 — 불필요하다는 확인 전 삭제 금지
- `data/private/`, `assets/private/`: 성경 원문·템플릿 등 비공개 자료
- `scripts/archive/`: 과거 보관 스크립트
- `experiments/` 및 `src/media_automation/_legacy_migration/`: 코드 비교·복구용 스냅샷

기존 Mac/Windows 별도 체크아웃, 운영 서버 및 운영 Supabase·OneDrive 상태는 이 저장소 정리만으로 변경되지 않는다.

추가 문서: [프로젝트 폴더 구조](../docs/repository_layout_20261022.md) · [전체 문서 길잡이](../docs/INDEX.md).
