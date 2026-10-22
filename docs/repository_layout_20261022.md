# 프로젝트 폴더 정리 기준 — 2026-10-22

이 문서는 기능 삭제나 예배별 디자인 통일 지시서가 아니다. **실제 교회 원본과 Mac/Windows의 작업 DB는 절대 자동 삭제·이관하지 않는다.** 정리는 GitHub **검수 브랜치 `fix/ui-workflow-20261015`의 코드**에 한정한다.

## 가장 먼저 열 파일

| 목적 | 공식 출발점 | 비고 |
|---|---|---|
| 로컬 웹 | `webapp.py` → `src/media_automation/web/server.py` | DB 명시·접근권한 확인 필요 |
| Mac 기존 실사용 실행 | `start.command` → `scripts/start_primary.py` | 기존 8876 및 DB 유지. 이 문서 작성 중 실행하지 않음 |
| 수요 명령어 | `wednesday.py` | 기존 예배별 흐름·4:3 악보 사용 규칙 유지 |
| 금요 명령어 | `friday.py` | Zoom 16:9와 대면 4:3 구별 |
| 주일 명령어 | `sunday.py` | 주일 PPT 입력과 주보 공동 정보 |
| 주보 단독 명령어 | `bulletin.py` | 사용자가 전달한 주보 우선, A4 4|1 / 2|3 접지 |
| 웹 UI 및 현재 로컬 API | `src/media_automation/web/original/` | 로컬/호스팅 분기 참조 |
| Google Cloud 웹 | `src/media_automation/cloud/server.py` | 현재 운영 이미지 보존, 검수 브랜치 자동 배포 금지 |
| Google Cloud 제작 Job | `src/media_automation/cloud/worker.py` | **독립 배포 단위**, 운영 Job 실행 금지 |
| 비공개 정적 UI 미리보기 | `deploy/cloud/Dockerfile.ui-preview` 및 `.github/workflows/ui-preview-sync.yml` | 오직 `media-ui-preview-1022` 서비스만 대상 |

## 폴더 역할: 섞어 쓰지 않는다

```text
media-automation/
├── AGENTS.md                 # 교회 제작/검수 상시 기준 (수정하지 않음)
├── webapp.py                 # 로컬 UI 진입점
├── wednesday.py              # 수요예배 CLI
├── friday.py                 # 금요 Zoom/대면 CLI
├── sunday.py                 # 주일예배 CLI
├── bulletin.py               # 인쇄용 주보 CLI
├── start.command             # Mac 로컬 실행기 (기존 실사용 경로)
├── src/media_automation/     # 현재 Python 패키지
│   ├── weekly_cli.py         # 수요/금요/주일의 공통 날짜·YAML 함수
│   ├── web/                  # UI/로컬 웹
│   ├── cloud/                # 호스팅 HTTP/인증/OneDrive/Job
│   ├── ppt/                  # PPTX 엔진
│   ├── bulletin/             # 주보 PDF 엔진
│   └── _legacy_migration/    # 복구용 보관본 (실서버 아님)
├── scripts/                  # 운영/점검/예배 제작 CLI와 도구
│   ├── archive/              # 과거 개발 보관본
│   └── audit_repository_layout.py # Git 추적 코드만 분류하는 읽기 전용 도구
├── tests/                    # 코드 검증, 별도 synthetic/클라우드 테스트
├── deploy/cloud/             # GCP/Supabase SQL 및 선택적 배포 스크립트
├── docs/                     # 설계·운영·검증 결과 (시점별 기록)
├── experiments/              # 과거 스냅샷. 'output' 이름에도 Git 추적 코드임
├── samples/                  # 예시 설정·합성 시험 데이터
├── data/                     # Git에 올려도 되는 공개 설정만
├── sources/                  # Git 무시. 원본 참고자료 읽기 전용
├── input/                    # Git 무시. 주간 입력·원본 복사 보존
└── output/                   # Git 무시. DB/완성본/임시 결과 보존
```

`experiments/desktop-webapp-20261010/output/`은 이름이 `output`이지만 **과거에 커밋된 코드 스냅샷**이며 실제 예배 완성본을 뜻하지 않는다. 이를 일반 `output/`과 혼동해서 지우지 않는다.

`src/media_automation/_legacy_migration/`은 단순히 쓸모없는 파일이 아니다. `scripts/run_original_blue.py`가 **명시적인 로컬 복구 시험**에 이 백엔드를 참조한다. 따라서 실제 사용처 확인 전 삭제·이동하지 않는다.

`scripts/archive/`의 이전 구현과 `experiments/` 파일도 비교·복구 참고 자산이므로 이번 정리에서 옮기거나 삭제하지 않았다.

## 이번에 실제로 변경한 코드

- 수요·금요·주일 CLI에 중복 구현되어 있던 `token()`, `load_yaml()`를 `src/media_automation/weekly_cli.py`로 통합했다.
- 이전 세 CLI의 호출 이름(`token`, `load_yaml`)과 날짜 파일명 규칙, `UNSET/NONE/VALUE` 입력 의미, 존재하지 않는 YAML의 `{}` 반환을 유지했다.
- 파일 읽기만 담당하는 공통 함수는 출력 파일·원본·서버·네트워크를 건드리지 않는다.
- 새 회귀 테스트 `tests/test_weekly_cli_shared.py`, 저장소 경계 테스트 `tests/test_repository_layout.py`, 읽기 전용 구조 점검 `scripts/audit_repository_layout.py`를 추가했다.
- 기존 중복 `run_script()`는 각 예배의 출력과 테스트 호환성 문제 때문에 그대로 뒀다. 별도 검수 없이 하나로 합치지 않는다.
- 기록한 시점까지 **이동·삭제한 원본 파일 0개**, 기존 운영/예배 PPT·PDF 제작 0건.

## Git 추적 폴더 점검 실행

```bash
python scripts/audit_repository_layout.py --check
python scripts/audit_repository_layout.py --json
python -m pytest -q \
  tests/test_weekly_cli_shared.py \
  tests/test_repository_layout.py \
  tests/test_friday_cli.py \
  tests/test_bulletin_cli.py
```

`audit_repository_layout.py`는 `git ls-files`를 통해 **Git에 추적되는 파일 목록만** 읽는다. 로컬 `sources/`·`input/`·`output/`의 실제 내용, 비밀 키, DB를 스캔하지 않는다. 과거 코드 복사본 중 바이트 단위로 동일한 후보만 신고하며 임의 삭제하지 않는다.

2026-10-22 [Repository Layout and Weekly CLI #1](https://github.com/moonaneul/media-automation/actions/runs/39730842031) 결과:

| 항목 | 결과 |
|---|---|
| 테스트 | **22 passed in 0.59s** |
| 현재 앱 코드 | 136개 |
| 유지보수/레거시 CLI | 73개 |
| 역사적 보관 파일 | 71개 |
| 원본/개인정보/DB 관련 Git 추적 경계 위반 | 0개 |
| 지원 진입점 누락 | 0개 |
| 바이트 동일 보관/현재 코드 쌍 | 2개(검토 후보일 뿐 삭제 승인 아님) |

자동화 `.github/workflows/repository-hygiene.yml`는 검수 브랜치의 관련 코드 변경 시 이 확인을 수행한다. Cloud Run/OneDrive/Supabase 인증정보를 사용하거나 운영 배포하지 않는다.

## 다음 정리 원칙

1. **중복 파일 이름만 보고 삭제하지 않는다.** 실제 호출 경로·실행 환경·복구 사용처를 찾아서 해당 파일의 존재 이유를 확인한다.
2. `scripts/` 중 실사용·단독 점검·실험·과거 보관을 구분하는 명령어 목록을 단계적으로 정리한다. 이전 명령어 경로를 바꾸려면 호환 실행기와 회귀 테스트를 먼저 제공한다.
3. `docs/` 과거 기록은 중요한 이력이다. 내용을 합치며 상충된 상태를 단정하지 않고 최신 상태와 문서 작성 당시를 별도 표기한다.
4. `sources/`, `input/`, `output/`, `assets/private/`, `data/private/`를 정리하려면 **각 Mac/Windows 작업 폴더의 Git status·DB·첨부·사용자 원본 검수**가 선행되어야 하며 GitHub 기록만 보고 삭제를 지시할 수 없다.
5. 금요 대면·Zoom, 주일·수요 PPT 디자인은 사용자 요청이 없는 한 통일하지 않는다. 실제 제작·미디어 재생 검수는 나중에 진행한다.


## 2차 스크립트 명령어 분류 및 중복 처리 (2026-10-22)

- [스크립트 사용 안내](../scripts/README.md)에서 루트 수요·금요·주일·주보 명령어, 직접/간접 참조된 하위 스크립트, 보관본, 수동 실행 시 주의할 명령어를 구분했다.
- `scripts/audit_script_usage.py`로 Git의 `scripts/` 내 Python 파일을 정적 연결만 기준으로 분류한다. **코드 실행/파일 정리 없음**.
- `scripts/refresh_sunday_song_checklist.py`와 `scripts/refresh_wednesday_song_checklist.py`의 정확한 파일명 검사 로직을 `src/media_automation/weekly_song_checklist.py`로 공통화했다. CLI 경로·옵션·출력 문구·누락 종료 상태는 유지했다.
- [Repository Layout and Weekly CLI #4](https://github.com/moonaneul/media-automation/actions/runs/39732522778): 저장소/스크립트 관계/악보 체크리스트 관련 **31 tests passed**.
- 73개의 정식 scripts Python 중 31개가 루트 명령어 참조 체인에 등장하고, 8개는 GitHub Actions에 명시되며, 36개는 정적 관계가 아직 확인되지 않았다. 분류가 겹칠 수 있고, **미참조가 곧 미사용·삭제 승인이 아니다.**
- 민감한 `sync_workspace.py push`(`git add --all`), `upload_missing_sources.py`(OneDrive 전송), 연결정보 내보내기/가져오기는 현재 작업에서 실행하지 않았다.
- 실제 예배 결과물 제작 및 육안 검수, 실 Microsoft 로그인, 클라우드 운영 배포는 계속 보류한다.
