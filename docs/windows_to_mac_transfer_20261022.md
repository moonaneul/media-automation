# Windows에서 MacBook으로 입력·원본 이전 (2026-10-22)

## 목적과 범위
- 코드: GitHub `fix/ui-workflow-20261015`에서 받는다.
- 로컬 원본: Windows 활성 프로젝트의 `sources/`, `input/`, `data/private/`, `assets/private/`만 ZIP에 묶는다.
- 제외: 기존 보관 프로젝트, `output/`, `.venv/`, Git 객체, SQLite DB, 비밀키/세션, 이전에 만든 PPT.
- ZIP과 작업 스크립트는 신뢰하는 USB/개인 파일 전송 수단으로 Mac에 옮긴다. 공개 GitHub·공개 파일 공유·채팅에 ZIP을 업로드하지 않는다.
- **기존 Windows 삭제는 Mac에서 데이터 검증과 실제 프로젝트 사용 확인 후 별도로 진행한다.**

## 1. Windows PowerShell (최신 활성 폴더에서)

```powershell
cd "$HOME\Documents\media-automation"
git status --short --branch
git pull --ff-only origin fix/ui-workflow-20261015

$bundle = "$HOME\Desktop\media-automation-win-inputs-20261022.zip"
.\.venv\Scripts\python.exe scripts\device_transfer.py pack --root . --bundle "$bundle"
.\.venv\Scripts\python.exe scripts\device_transfer.py verify --bundle "$bundle"
Get-FileHash -LiteralPath "$bundle" -Algorithm SHA256
Copy-Item -LiteralPath ".\scripts\device_transfer.py" -Destination "$HOME\Desktop\device_transfer.py"
```

pack 명령은 **원본을 삭제·이동하지 않고**, ZIP 파일이 이미 존재할 경우 덮어쓰지 않는다. `pack`의 파일 수와 바이트, `verify` 파일 수를 확인하고 ZIP SHA-256을 기록한다. 오류(키·DB·심볼릭 링크·Git LFS 포인터)가 발생하면 **해결 전 삭제 금지**.

Desktop의 ZIP과 `device_transfer.py`를 Mac의 `~/Downloads/`로 수동 전송한다.

## 2. Mac 터미널 (기존 Mac 프로젝트를 변경하지 않음)

```bash
cd ~/Documents
ls -d media-automation* 2>/dev/null
if [ -d media-automation ]; then
  git -C media-automation status --short --branch
  git -C media-automation log -1 --oneline
fi

python3 ~/Downloads/device_transfer.py verify \
  --bundle ~/Downloads/media-automation-win-inputs-20261022.zip

mkdir -p ~/Documents/media-automation-win-staging-20261022
python3 ~/Downloads/device_transfer.py import \
  --bundle ~/Downloads/media-automation-win-inputs-20261022.zip \
  --destination ~/Documents/media-automation-win-staging-20261022

python3 ~/Downloads/device_transfer.py import \
  --bundle ~/Downloads/media-automation-win-inputs-20261022.zip \
  --destination ~/Documents/media-automation-win-staging-20261022 --copy

python3 ~/Downloads/device_transfer.py import \
  --bundle ~/Downloads/media-automation-win-inputs-20261022.zip \
  --destination ~/Documents/media-automation-win-staging-20261022
```

마지막 결과에서 `copy_candidates=0`, `conflicts=0`, `identical_files=files`이어야 한다. Windows의 ZIP SHA-256과 Mac verify의 `zip_sha256` 값도 같아야 한다. 검수용 staging 폴더는 기존 Mac 코드·자료를 덮어쓰지 않는다.

## 3. Mac의 실제 활성 코드와 합치기

기존 Mac 프로젝트에는 Windows에 없던 DB·소스·로컬 변경이 있을 수 있으므로 **현재 Git 상태와 DB/워크파일 확인 전에 브랜치 변경·덮어쓰기·기존 폴더 삭제 금지**. 최신 검수 코드를 새 checkout에 준비할 경우:

```bash
cd ~/Documents
git clone --branch fix/ui-workflow-20261015 --single-branch \
  https://github.com/moonaneul/media-automation.git \
  media-automation-migrated-20261022
```

이 별도 checkout으로 데이터를 가져오기 전에, Mac 고유 원본/DB를 보존하고 활성 폴더를 선택한다. 데이터 병합이 승인된 대상으로 확인되면 `import --destination <선택한_프로젝트> `로 미리보기하고 `conflicts=0`일 때만 `--copy`를 붙인다. 이 도구는 **기존 같은 이름 파일을 덮어쓰지 않는다**.

새 컴퓨터에서 정상 설치·필요 원본 열람·기능 테스트가 확인되어야 이전 완료다.

## 4. Windows 삭제 보류 조건

- Mac에 ZIP과 스크립트가 있고 독립 ZIP SHA-256 및 내부 100% 해시가 일치
- Mac staging 및 선택한 실제 활성 프로젝트에서 필요한 자료가 확인됨
- Mac 고유 입력/DB가 보존되고 앱 기능 테스트를 통과
- 별도 악보 라이브러리가 Windows에만 남지 않았는지 확인
- 사용자가 생성본/Windows 옛 출력이 불필요하다고 최종 판단함

위 조건을 만족하기 전에는 Windows의 `media-automation` 및 `media-automation-archive-20261022`를 삭제하지 않는다. 만족한 뒤에는 폴더 경로를 다시 확인하고 삭제 미리보기(`Remove-Item -WhatIf`)를 실행하여 검토한 다음 삭제한다. Windows 기기를 다른 사람에게 양도할 예정이라면 프로젝트 폴더 삭제와 별도로 OS 초기화·개인정보 제거가 필요할 수 있다.
