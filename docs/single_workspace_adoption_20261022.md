# Windows 2개 체크아웃을 **1개 활성 프로젝트**로 정리하기 — 2026-10-22

## 결정: 최신 코드는 검수 브랜치를 채택, 기존 원본은 보관

실제 조사 결과:

- Windows 기존 `C:\Users\SSAFY\Documents\media-automation`: 브랜치 `feature/friday-json-bible`, 사용자 공유 검사 당시 커밋 `ce29bbb34faf`; `git status` 깨끗함. 보호 데이터 경로로 분류된 **추적 파일 361개**, Git ignore 가드 불충분, 기본 자동 탐색 DB 없음. 이는 파일이 불필요하거나 실제 개인 비밀이라는 뜻이 아님.
- Windows 새 `C:\Users\SSAFY\Documents\media-automation-ui-review`: `fix/ui-workflow-20261015`; 최신 CI/웹/작업 정리 기능 포함, Git working tree 깨끗하고 기존 주간 DB 기본 위치는 없음.
- 원격 `feature/friday-json-bible` 및 UI 브랜치 Git tree 비교에서 **기존 브랜치에만 있는 앱/제작 Python 코드 파일은 0개**. UI 브랜치에 **없는 비원본 경로의 유일한 YAML은 `data/bible_library.yaml`(생성용 성경 캐시)**. 기존 브랜치에만 있는 나머지는 과거 주간 입력/출력, 미디어·참고자료다. 두 브랜치 모두 가지고 있는 코드 중 **다르게 수정된 파일**이 있으므로 예전 브랜치 전체를 덮어 병합하면 최신 수정이 사라질 수 있다.
- 원격 기존 기능 브랜치의 커밋은 로컬 Windows 체크아웃보다 앞선 상태일 수 있다. 숫자·파일 형식만 보고 사용자의 로컬 자료가 같은 상태라고 추정하지 않는다.

**코드 채택 결정:** 현재 최신 코드 `fix/ui-workflow-20261015`를 향후 단일 활성 체크아웃으로 사용한다. 이는 오래된 feature Git 히스토리를 합쳤다는 뜻이 아니다. 사용자가 사용할 **폴더 이름**은 최종적으로 `media-automation` 한 개로 통일하되, 오래된 폴더는 내용을 검수할 때까지 이름만 변경한 **보관 폴더**로 유지한다. 실제 디렉터리 이동은 Windows 사용자가 실행한다.

**예배 데이터 채택 결정:** GitHub checkout의 파일과 로컬 데이터는 별개다. 이전 주간 `sources/`, `input/`, `data/private/`, `assets/private/` 중 필요한 내용만 **덮어쓰기 없는 방식으로 복사**하고, `output/`은 기본 복사하지 않는다. SQLite DB·OneDrive 세션·토큰은 일반 파일 복사 대상에서 제외한다.

## A. 먼저 옛 데이터의 복사 필요 여부 확인 (현재 실행 가능, 기본 읽기 전용)

Windows Git Bash:

```bash
cd ~/Documents/media-automation-ui-review
git status --short --branch
git pull --ff-only origin fix/ui-workflow-20261015

python scripts/prepare_single_workspace.py \
  --source ../media-automation \
  --destination .
```

**마지막 Python 명령은 기본 DRY_RUN이다.** 원본과 대상 파일은 그대로 두며, 다음 숫자만 보고한다.

- `copy_candidates`: 아직 새 체크아웃에 없는 파일
- `conflicts`: 같은 이름이지만 다른 파일 (절대 자동 덮어쓰지 않음)
- `identical_files`: 동일한 SHA-256로 이미 존재
- `lfs_placeholders_skipped`: 실제 미디어 대신 남아 있는 Git LFS 포인터
- `blocked_credentials_and_live_databases`: DB/키/연결정보 등 복사 제외
- `candidate_bytes`: 지금 옵션에서 누락 파일을 복사할 경우 필요한 바이트 수

`lfs_placeholders_skipped`가 0이 아니면 LFS 포인터를 실제 미디어 파일로 오해하지 않는다. 파일을 사용자 허락 없이 내려받거나 대체하지 않고 **자료 보관 위치를 확인**한다.

사용자가 원래 생성본까지 남기고 싶다면 별도로 **복사 후보만** 계산한다.

```bash
python scripts/prepare_single_workspace.py \
  --source ../media-automation --destination . --include-output
```

기존 완료 PPT가 불필요하다면 `--include-output`을 사용하지 않는다. 하지만 이름에 `output`이 있더라도 승인된 검수 상태/백업/원본이 있는지 확인하기 전 원래 output 폴더를 삭제하지 않는다.

## B. 필요한 입력만 실제 복사

**A 단계에서 충돌과 LFS 포인터·심볼릭 링크가 없는 것을 확인한 경우에만** 아래를 실행한다. 파일을 덮어쓰지 않고 원본의 파일명과 바이트를 보존하여 복사하며, SHA-256를 검증한다.

```bash
python scripts/prepare_single_workspace.py \
  --source ../media-automation \
  --destination . \
  --copy
```

이 명령은 **DB·OneDrive 연결·토큰·Git 디렉터리·가상환경·기존 output 생성본을 자동 이관하지 않는다.** 기존 원본 삭제, Git 브랜치 이동, 서버 변경도 하지 않는다.

`conflicts`/LFS 포인터가 보고되면 복사를 강행하지 말고 **필요한 자료만 따로 확인**한다. 기존 자료가 복구용으로만 필요하다면 아예 복사하지 않고 보관 폴더에 남겨도 된다.

## C. 한 개의 활성 폴더로 변경 (B와 상태 검수 후, Windows에서만)

이름 변경은 새 코드가 정상 작동하고 다른 프로그램이 기존 폴더를 사용 중이지 않은지 확인한 **후** 진행한다. 특히 원래 폴더의 `.venv`는 이동 뒤에도 기존 Windows 경로를 가리킬 수 있으므로 복사하지 않는다.

1. 현재 열려 있는 원래 미디어 앱·백그라운드 서버를 사용자가 종료한다.
2. Git Bash에서 `deactivate`로 기존 `.venv`를 종료한다.
3. `cd ~/Documents` 이후 다음 폴더명이 실제로 **없는지** 검사한다.
   `test ! -e media-automation-archive-20261022`
4. 조건을 확인하면 기존 폴더를 **삭제하지 않고 보관 이름으로 변경**한다.
5. 검수용 폴더를 최종 `media-automation`으로 변경한다.
6. 새 위치에서 독립된 Python 가상환경을 생성한다.

실행 예시 (**사전 점검 없이는 복사·붙여넣기 실행 금지**):

```bash
deactivate
cd ~/Documents
test ! -e media-automation-archive-20261022 || { echo 'Archive already exists'; exit 1; }
test -d media-automation && test -d media-automation-ui-review || { echo 'Missing checkout'; exit 1; }
mv media-automation media-automation-archive-20261022
mv media-automation-ui-review media-automation
cd media-automation
py -3 -m venv .venv
source .venv/Scripts/activate
python -m pip install -e ".[dev]"
python scripts/check_workspace_split.py
```

두 번의 rename 전/후에 앱이 살아 있거나 파일이 잠겨 있으면 중단하여 상태를 확인한다. `mv`는 Windows 운영 파일 시스템의 권한과 열린 파일에 따라 실패할 수 있으므로 성공을 전제하지 않는다. 새 체크아웃에 기존 `.venv`가 있다면 가상환경 생성에 앞서 따로 점검한다.

## D. 완료 기준 및 금지 사항

- [ ] 새 `media-automation` 경로에서 Git 브랜치가 `fix/ui-workflow-20261015`, 깨끗한 작업 상태임을 확인
- [ ] 입력/찬양/자료를 사용하려면 명시적으로 복사하거나 새 파일을 제공, SHA-256 및 연결경로 확인
- [ ] 로컬 DB가 필요할 경우 **어느 DB가 원본인지 별도 확정**하고 안전한 백업/이관 절차 승인
- [ ] 새 `.venv`의 Python 및 `pytest` 정상 작동 (실제 예배 제작·화면 검수와 별개)
- [ ] 이전 원본 `media-automation-archive-20261022`를 삭제하지 않고 보존
- [ ] 최종 Mac의 동일 코드 버전 적용은 **별도 로컬 상태 점검 후** 진행
- [ ] 운영 Cloud Run, OneDrive, Supabase 서비스와 비밀정보 변경 없음

**절대 하지 말 것:** 원래 `feature/friday-json-bible` 폴더에서 `git switch fix/ui-workflow-20261015`를 바로 실행하지 않는다. 예전 브랜치에 Git으로 추적된 `input/output` 파일들이 새 브랜치에 없으므로, 브랜치 변경이 **기존 파일을 실제로 제거할 수 있다**. 또한 `git reset --hard`, `git clean -fd`로 정리를 시도하지 않는다.

새 검수용 코드 채택/옛 데이터 보관/로컬 폴더 이름 변경은 세 가지 별개 확인 항목이다. 이 문서와 테스트가 존재한다는 사실만으로 Windows 폴더가 이미 옮겨졌다고 말하지 않는다.
