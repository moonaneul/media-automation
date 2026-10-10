# 다른 컴퓨터에서 이어서 작업하기

성경 데이터(`data/private/`), 공통 음원(`assets/private/`), 주간 영상과 안내(`input/`),
중간 입력과 완성 PPT(`output/`), 원본 자료(`sources/`, `source/`)도 함께 동기화한다.
영상·음원·Office 문서·PDF·ZIP은 Git LFS로 저장한다.
`private`는 기존 폴더 이름이며 GitHub 접근 권한을 제한하는 기능이 아니다.
현재 공개 저장소에 push하는 파일은 공개된다.

## 지금 작업한 컴퓨터에서 한 번 올리기

Git LFS를 설치한다. Git for Windows에 포함돼 있다면 `git lfs version`이 바로 동작한다.
저장소 폴더에서 실행한다.

```bash
git pull --ff-only
python friday.py complete 2026-10-09
python scripts/sync_workspace.py push --message "Save Friday Zoom 2026-10-09 and media"
```

`complete`를 다시 실행하면 미디어 경로도 다른 컴퓨터에서 사용할 수 있는 상대 경로로 갱신된다.
동기화 명령은 무시되지 않는 작업 변경 전체를 커밋하고 현재 브랜치에 push한다.
LFS 업로드 오류가 발생하면 완료되지 않은 상태다. 오류를 해결하고 같은 push 명령을 다시 실행한다.
저장소 밖에 있는 미디어는 `input/` 또는 `assets/` 안에 작업 복사본을 두어야 함께 동기화된다.
PowerPoint에서 완성 PPT를 열어둔 경우 닫고 실행한다.

## 새 컴퓨터에서 처음 시작

Git, Git LFS, Python 3.11 이상을 설치한다. 실제 재생 검수에는 Windows PowerPoint가 필요하다.

```bash
git lfs install
git clone --branch feature/friday-json-bible https://github.com/moonaneul/media-automation.git
cd media-automation
git lfs pull
powershell.exe -ExecutionPolicy Bypass -File scripts/setup_windows.ps1
source .venv/Scripts/activate
python friday.py complete 2026-10-09
```

위 명령은 Windows Git Bash 기준이다. GitHub 로그인은 Git Credential Manager 안내에 따른다.
성경·영상·음원을 별도로 복사할 필요 없이 저장소에서 받는다.

## 이후 작업

시작할 때:

```bash
python scripts/sync_workspace.py pull
```

마칠 때:

```bash
python scripts/sync_workspace.py push --message "Save worship work"
```

두 컴퓨터가 같은 파일을 동시에 수정한 경우 먼저 변경사항을 보관하고 충돌을 해결한다.
동기화 스크립트는 변경사항을 버리거나 강제 push하지 않는다.
가상환경·캐시·임시 파일·Office 잠금 파일·인증정보는 계속 제외한다.

## 2026-10-09 작업 상태

금요 Zoom 안내, JSON 성경 조회, 고정 개인 기도, 미디어 9곳 연결, 기도 클릭 애니메이션,
기도제목 아래 성경 구절 28pt 표시까지 구현했다.
윈도우 자동 QA와 테스트 226개가 통과했고 2개는 건너뛰었다.
실제 PowerPoint 화면과 재생 확인은 자동 QA와 별도로 진행한다.
