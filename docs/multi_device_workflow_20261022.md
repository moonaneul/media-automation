# Mac·Windows·GitHub·Cloud Run 작업 분리 및 안전한 동기화 가이드

2026-10-22 기준, **코드만 중앙 GitHub에서 관리**하고, 개인 PC의 입력 DB·원본·생성본은 별도로 취급한다. 이 문서는 기존 자료의 저장 장소를 새 서비스로 옮기는 결정을 내리지 않는다. 기존 서버나 작업 파일을 중지/삭제/이관하지 않았다.

## 1. 서로 다른 종류의 자료를 하나의 '동기화'로 취급하지 않는다

| 범위 | 실제 목적 | 지금의 기준 | 자동 처리 여부 |
|---|---|---|---|
| GitHub `moonaneul/media-automation` | Python/JS·웹 UI·CI·문서·테스트 코드의 변경 이력 | 현재 UI·구조 검수: `fix/ui-workflow-20261015` / Draft PR #15 | 코드만 명시적으로 push/pull |
| Mac 기존 `media-automation` | 기존 로컬 실사용·DB·소스 파일 보유 가능 | `start.command`, 8876 실사용 사례가 있었음 | **건드리지 않음**. 현재 실행·브랜치·DB 존재 여부는 개인 Mac에서 직접 확인 필요 |
| Mac `media-automation-ui-review` | 별도 UI/통합 코드 검수용 | 18877 / `output/ui-review/work.db` 활용 기록이 있음 | 기존 실사용 폴더와 자동 병합·복사 안 함 |
| Windows 기존 `media-automation` | 과거 개발 및 Windows PowerPoint 재생 시험 환경 | 미커밋 코드와 로컬 자료가 있을 수 있음 | **강제 reset·checkout·덮어쓰기 금지** |
| Windows `media-automation-ui-review` | 별도 최신 코드 검수용(설치 시) | `fix/ui-workflow-20261015` 권장 검수 브랜치 | 코드만 가져옴, 이전 DB는 자동 등장하지 않음 |
| Cloud Shell | GCP의 읽기 전용 상태 확인 또는 **승인받은** 배포 명령 실행 | `/tmp`에 만든 임시 Git clone은 영구 보관본이 아님 | 정식 DB/원본 저장소로 사용 금지 |
| 비공개 Cloud Run `media-ui-preview-1022` | 정적 HTML/CSS/JS 화면 검수 | 검수 브랜치에서 제한된 자동 배포 | 실제 제작 API·OneDrive 연결 **없음** |
| Cloud Run `media-automation` 및 Job `media-production` | 기존 호스팅 웹/제작 단위 | 2026-10-22 당시 기존 이미지 유지 확인 | 검수 브랜치에서 자동 배포 **안 함** |

**Git이 맞춘 것은 코드 버전이지 주간 예배 내용이 아니다.** Git의 브랜치·SHA가 같아도 두 컴퓨터의 `output/*.db`, `work.files/`, `work.generated/`, 성경 JSON, OneDrive 로그인 상태는 같다고 할 수 없다.

## 2. 반드시 따로 다룰 데이터

- `sources/`: 교회가 제공한 원본 및 참고자료. 수정·이동·삭제하지 않는다.
- `input/`: 이번 주 안내, 악보 PPT, 찬양 영상 등. 사용자가 지정하지 않은 이전 주 자료 자동 승계 금지.
- `output/`: 로컬 DB와 재생성 파일 외에 **승인된 검수 결과, 입력·원본의 연결 기록, 검수 리포트**가 있을 수 있다. `output`이라는 이름만 보고 일괄 삭제하지 않는다.
- `data/private/` 및 `assets/private/`: 개역개정 원문/검수 원본·템플릿 등 비공개 자료.
- `work.onedrive/`, `.env*`, 암호화 연결 파일: 토큰, 비밀, Microsoft 연결정보를 포함할 수 있다. 기기 간 일반 ZIP/Git/채팅 전송 대상이 아니다.
- OneDrive: 실제 연결되어 있는 **개인 원본 조회용 Drive**와 **미디어팀 완료본 공유폴더**를 구별한다. 별도 Microsoft 시험 계정이 없는 상태이므로 실제 원격 업로드/삭제 시험은 보류한다.
- Supabase: 호스팅 작업 공간. 로컬 SQLite와 운영 Supabase 간 자동 양방향 동기화가 완성됐다고 가정하지 않는다.

## 3. 코드 버전과 로컬 자료의 안전한 확인 (읽기 전용)

각 PC에서 **해당 체크아웃의 루트**로 이동한 후 아래를 실행한다.

```bash
# Mac 또는 Windows의 Python 환경에서 (작업 폴더 안):
python scripts/check_workspace_split.py
python scripts/check_workspace_split.py --json
```

Windows PowerShell에서는 `python`을 `py -3`으로 바꿔도 된다. 기존 파일을 움직이지 않고 Git의 분기·커밋·수정 유무, 민감자료가 Git에서 제외되는지, 선택된 로컬 DB 경로의 **존재 여부만** 출력한다.

비공개 결과를 다른 PC에서 비교하려면 **서로 같은 검수 코드 버전**을 받은 뒤 아래처럼 사용한다. 전송 수단은 사용자가 선택하며, 실제 코드/DB/예배 파일을 이 단계에서 전송하지 않는다.

```bash
# Mac: 사용자가 지정한 안전한 폴더에 코드 상태 요약만 저장
python scripts/check_workspace_split.py --json > /path/you/choose/mac-code-state.json
```

```powershell
# Windows PowerShell: 사용자 본인이 지정한 폴더에 JSON만 저장
py -3 .\scripts\check_workspace_split.py --json | Set-Content -Encoding utf8 "C:\path\you\choose\windows-code-state.json"
```

Mac에서 Windows 보고서를 사용하거나 반대 방향으로 안전하게 가져왔다면:

```bash
python scripts/check_workspace_split.py --json --compare /path/to/other-device-code-state.json
```

비교 결과는 브랜치와 코드 커밋이 같은지, 두 체크아웃에 미커밋 변경이 있는지, 양쪽에 DB 경로가 존재하는지만 표시한다. **실제 DB 내용/버전 일치나 원본 파일 해시는 검사하지 않는다.** 보고서에는 토큰·성경 본문·DB의 경로·내용을 출력하지 않지만 Git 브랜치와 커밋 식별자가 들어 있으므로 불특정 공개 게시물에는 넣지 않는다.

## 4. 코드만 안전하게 갱신하는 방식

1. 현재 컴퓨터에서 `git status --short --branch`로 브랜치와 변경사항을 확인한다. 변경 내용이 있으면 **우선 저장·검토**하고 `git reset --hard`, `git clean -fd`, 강제 checkout을 실행하지 않는다.
2. 검수용 브랜치의 코드만 갱신하고 싶다면 검수용 별도 체크아웃에서 `git fetch origin` 뒤, **현재 브랜치가 정확히 `fix/ui-workflow-20261015`이고 충돌·미커밋 변경이 없는 경우에만** `git pull --ff-only origin fix/ui-workflow-20261015`을 고려한다.
3. 수정한 코드를 GitHub에 보낼 때는 `git diff --stat`, `git status --short`를 검토한 다음 **필요한 코드 파일만** `git add 경로`로 지정한다. `git diff --cached --stat`와 `git diff --cached`로 민감정보가 스테이징되지 않았는지 확인한 후 커밋·푸시한다.
4. `scripts/sync_workspace.py push`는 **현재 구현에서 `git add --all` + commit/push**를 호출한다. 코드-데이터 분리가 확인되기 전에는 **사용하지 않는다**. Git ignore는 잘못된 `git add -f`나 이미 추적된 파일을 자동으로 보호하지 않는다.
5. `git lfs pull`은 저장소가 추적하는 대형 원본을 다운로드할 수 있으므로 코드만 확인하려는 작업에는 불필요하다. `scripts/sync_workspace.py pull`은 Git LFS도 자동 실행하므로 코드를 가볍게 맞추는 목적으로 사용하지 않는다.

## 5. 나중에 로컬 작업 데이터를 실제로 이관할 경우

- 먼저 어느 컴퓨터/DB가 실제 사용자 입력의 **권위 있는 원본**인지 정한다. 이를 확인하기 전에는 DB A를 B에 덮어쓰거나 여러 DB 내용을 자동 병합하지 않는다.
- 웹 서버가 사용 중인 SQLite 파일을 무작정 복사하지 않는다. 종료 후 백업/일관성 확인 또는 SQLite backup API 등 안전한 절차를 별도로 승인받아 사용한다.
- `work.db`와 그 DB가 참조하는 `work.files/`의 연결/파일 해시를 함께 확인하고, `work.generated/`는 재생성이 가능한지, 검수·승인 증빙이 남는지 별도로 구분한다.
- Microsoft OAuth 세션과 암호화 키는 DB와 구별한다. 비공개 연결 토큰은 일반적인 파일 동기화 대상이 아니다. 가능하면 새 장치에서 재인증한다.
- 실 Supabase나 교회 OneDrive의 스키마/데이터/폴더를 이관 과정에서 자동으로 수정하지 않는다.
- 데이터 이동이 완료되었다고 말하려면 양쪽 DB의 입력·검수 상태, 필수 첨부, 실제 읽기 기능과 새 기기 원본/폰트 접근을 **별도로 검증**해야 한다.

## 6. 완료와 미완료 구분

- [x] GitHub 코드의 실제 폴더/진입점 구조 및 2차 스크립트 사용 관계 분류
- [x] Mac·Windows 체크아웃에서 재사용할 읽기 전용 상태 점검 도구
- [x] Git에서 원본/DB/비공개 폴더를 잘못 추적하는 회귀 검사
- [x] 양쪽의 **코드 분기·커밋**을 비교할 수 있는 JSON 보고 형식
- [ ] 실제 Mac 및 Windows 각 컴퓨터에서 최신 상태 점검 실행
- [ ] 두 컴퓨터에 동일한 로컬 DB·원본/연결 상태가 있는지 확인 (현 단계에서는 의도적으로 미수행)
- [ ] 어떤 저장소를 단일 데이터 원본으로 삼을지 결정 (사용자 승인 전 미결정)
- [ ] 실제 예배 제작·PowerPoint 재생/인쇄물의 육안 검수 (사용자 요청에 따라 보류)
- [ ] 운영 웹/Job 업데이트 (명시적 승인 전 보류)

## 자동 검증

```bash
python scripts/check_workspace_split.py --check
python -m pytest -q tests/test_workspace_split.py
```

`--check`는 Git에서 추적되는 DB·토큰이 있거나 필수 무시 규칙이 깨졌을 때 실패한다. DB가 없는 **깨끗한 CI 코드 체크아웃 자체는 실패하지 않는다**. 이 점검은 OS별 로컬 자료의 동등성이나 실제 로그인 여부를 증명하지 않는다.
