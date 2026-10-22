# Windows 전환 인수인계 — 2026-10-22

## 범위 및 현재 기준
- GitHub: https://github.com/moonaneul/media-automation
- **Draft PR #15**: https://github.com/moonaneul/media-automation/pull/15
- 코드 브랜치: `fix/ui-workflow-20261015`. `main`/운영 Mac 8876은 변경하지 않는다.
- Mac 실제 검수용 checkout: `/Users/moonaneul/Documents/media-automation-ui-review`
- Mac 검수용 DB: `output/ui-review/work.db`, 앱 포트 `18877`.
- 기존 Windows 코드 폴더: `C:\Users\SSAFY\Documents\media-automation` (과거 main/개발 작업의 미커밋 변경 가능성 있음). **삭제·덮어쓰기·강제 reset 금지**.
- Mac에서 확인한 수요예배 `요 1~3장` 장 범위 해석 오류 해결: 요 1장 51절, 2장 25절, 3장 36절, 합계 112절. 사용자가 실제 Mac PPT에서 오류 해결 확인함.
- 성경 검수 기록은 개역개정 독립 원문 대조를 의미하지 않음: 검증받은 본문은 재사용하되 새 구절/내용 변경은 직접 검수. 수요·주일은 한 절당 한 화면.
- 미디어팀 OneDrive 완료본은 **기존** 팀 공유 폴더(주보 `00.주보`, 주일 `01.주일예배/01.예배 PPT/{YYYY}년`, 수요 `02.수요예배`, 금요 `03.금요예배`)에만 저장. 개인 OneDrive는 악보/Zoom 원본 조회용. 실제 폴더 접근·업로드 여부와 Microsoft API 응답은 별도로 검증. 기존 파일/폴더는 이동·삭제·생성하지 않는다.
- 한 주의 날짜/담당자/찬양/말씀/광고를 과거 자료에서 자동 승계하지 않는다.

## 1. Windows에서 최신 코드 안전하게 시작 (PowerShell)

기존 Windows 프로젝트 `media-automation`을 건드리지 않고 **별도 폴더** `media-automation-ui-review`로 클론한다. Git LFS에 과거 대용량 미디어가 있으므로 이 작업에서는 다운로드하지 않는다. 해당 경로가 이미 있으면 **클론을 다시 하지 말고 상태를 확인**한다.

```powershell
Set-Location "$HOME\Documents"
Test-Path ".\media-automation-ui-review"
```

결과가 `False`일 때에만 다음을 실행한다.

```powershell
$env:GIT_LFS_SKIP_SMUDGE = "1"
git clone --depth 1 --single-branch --branch fix/ui-workflow-20261015 https://github.com/moonaneul/media-automation.git media-automation-ui-review
Remove-Item Env:\GIT_LFS_SKIP_SMUDGE -ErrorAction SilentlyContinue
Set-Location ".\media-automation-ui-review"
git status --short
git log -1 --oneline
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q tests/test_wednesday_john_chapters.py tests/test_durable_bible_review_cache.py
```

기존 폴더가 **이미 있거나 git status가 깨끗하지 않다면 강제 checkout/reset하지 않는다**. 변경사항을 출력해 정리한 뒤 이어간다. `setup_windows.ps1`는 테스트 전체를 실행하기 때문에 원본 폰트/템플릿이 없는 PC에서는 알려진 실패가 있을 수 있다. `py -3`은 Python 3.11 이상이어야 한다.

## 2. Windows에서 예전 예배 입력까지 이어 쓰려면 (로컬 데이터 별도 전송)

**GitHub에는 작업 DB·PPT·원본·OneDrive 암호화 연결이 자동 올라가지 않는다.** 코드만 받아서 새 `work.db`를 생성하면 Mac의 지난 입력/검수 상태가 보이지 않는다. 데이터도 계속 써야 한다면:

1. Mac 18877 서버를 `Control+C`로 종료하고, 원본을 변경하지 않는 별도 백업을 만든다.
2. Mac **검수 폴더** `/Users/moonaneul/Documents/media-automation-ui-review/output/ui-review/`에서 다음 자료만 복사한다.
   - `work.db` (입력·검수·곡목록/연결 상태)
   - `work.files/` (DB에 등록된 원본, 파일 크기 큼)
   - `work.generated/` (생성본 PPTX/PDF 및 제작 리포트, 파일 크기 큼)
   - 사용 중인 `data/private/bible_fixed.json` 및 명시적 `MEDIA_BIBLE_FILE`/성경 검수 원본이 있으면 **해당 출처를 확인하여 별도** 복사한다. 가져올 수 없는 성경 본문은 추정해서 채우지 않는다.
3. 사용자 본인만 접근할 수 있는 전송 수단으로 Windows에 가져온 후, 아래와 같은 위치에 **새 폴더**로 둔다.
   - `<Windows-review-checkout>/output/ui-review/work.db`
   - `<Windows-review-checkout>/output/ui-review/work.files/`
   - `<Windows-review-checkout>/output/ui-review/work.generated/`
   - 성경 데이터는 repo의 `data/private/` 등 기존 코드가 참조하는 비공개 경로에 둔다.
4. **`output/ui-review/work.onedrive/`는 위 백업에 포함하지 않는다.** MS 앱 Secret·토큰·암호화 키가 있으므로 GitHub, 채팅, 공유 ZIP에 업로드하지 않는다. 새 Windows 앱에서 OneDrive에 다시 로그인하고 교회 미디어팀 공유 완료본 연결을 다시 확인한다. 비공개 credential transfer는 별도 암호화·승인 흐름을 통해서만 진행한다.
5. 이관할 Windows `work.db`가 이미 있다면 바로 덮어쓰지 않는다. 별도의 파일명/폴더로 보관하고 차이를 검토한다. Mac과 Windows에서 동일 DB를 동시에 수정하지 않는다.

Mac에서 우선 코드만 옮기고 싶다면 이 단계는 건너뛰어도 된다. 단, 기존 주간 정보는 보이지 않으므로 **테스트용 빈 DB로 작업 중이라고 명시**해야 한다.

## 3. Windows 웹앱 실행

Windows PowerShell에서:

```powershell
Set-Location "$HOME\Documents\media-automation-ui-review"
Test-Path ".\output\ui-review\work.db"
```

이 값이 `True`라면:

```powershell
.\.venv\Scripts\python.exe webapp.py --port 18877 --database ".\output\ui-review\work.db"
```

브라우저: http://127.0.0.1:18877/

`False`라면 Mac 검수 입력을 가져오지 않은 상태다. 앱을 실행해 새 빈 DB를 만든다고 Mac 작업이 따라오는 것은 아니다.

## 4. 검수 및 다음 작업

- 저장 DB가 정확히 Mac에서 이관된 버전인지, 예배 날짜·입력·검수 상태가 있는지 확인한다.
- 2026-10-21 수요예배의 `요 1~3장`이 기존 결과에서 올바르게 출력됐다는 사실은 Mac에서 사용자가 확인했음. Windows에서 **과거 PPT 자동 승계/재제작을 임의 실행하지 않고**, 해당 주 입력을 열어서 112절/한 절 한 화면·본문 누락/중복·개역개정·세례→침례·실제 렌더링을 확인한다.
- PDF A4 가로 2장 `4|1`/`2|3` 및 실제 인쇄는 별도 검수.
- 금요 Zoom MP4/MP3 실제 재생, 금요 대면 악보 PPT의 PowerPoint Windows 화면 재생/보존 검수는 별도로 한다.
- 이전 OneDrive 완료본 경로, 인증 및 네 폴더 연결은 Windows에서 별도로 확인한다.
- Windows에서 수정한 코드만 Draft PR #15에 커밋하며, `scripts/sync_workspace.py push`처럼 `git add --all`을 수행하는 명령은 **비공개 실데이터 검토 전 실행하지 않는다**. 원본/DB/토큰/완성본을 Git에 커밋하지 않는다.
- 코드 갱신은 GitHub Draft PR #15로 이어가고, 맥 검수 DB 변경은 자동 동기화되지 않으므로 명시적 백업/전송으로 관리한다.
