# 금요 Zoom Windows 인수인계

현재 상태: `feature/friday-macos-operations` 브랜치에서 Mac 클립보드 지원과 동일 기도 음원 공유 파일 지원까지 구현했다.

Mac에서 2026-09-18 과거 Zoom PPT의 내장 미디어를 검사한 결과:

- MP4 5개: ZIP/CRC 무결성 통과
- MP3 4개 중 `media1.mp3`: CRC 오류
- `media1.mp3`는 slide 1 예배 준비 음원
- `media9.mp3`는 slide 16, 17에서 같은 파일을 공유
- 예배 준비 음원은 현재 기본 제외
- 공동체 기도/개인 기도는 같은 주에 사용자가 명시한 경우 `community_personal_prayer.mp3` 하나를 공유할 수 있음

이 작업은 과거 9/18 자료를 새 주차에 자동 승계하기 위한 것이 아니다. 현재 빌더가 실제 과거 한 주를 재현할 수 있는지 확인하는 회귀 테스트다.

## Windows에서 준비

저장소에서:

```powershell
git fetch origin
git switch feature/friday-macos-operations
git pull
```

가상환경이 이미 있으면 활성화한다. 없으면 프로젝트의 기존 설치 절차에 따라 생성한다.

## 별도로 가져올 파일

현재 9/18 회귀 테스트를 이어가기 위해 Git 외부에서 필요한 파일은 **하나**다.

```text
20260918_금요예배(줌).pptx
```

Mac에서 추출해 둔 8개 MP4/MP3를 별도로 옮길 필요는 없다. 아래 전용 스크립트가 원본 PPTX에서 CRC 정상 미디어만 다시 추출하고 테스트 입력을 재구성한다.

`input/`, `output/`, `*.pptx`, `*.mp3`, `*.mp4`, `data/private/`는 Git에 올라가지 않으므로 로컬에서만 존재한다.

## 9/18 회귀 테스트 한 번에 실행

PowerShell에서 원본 PPTX 경로를 지정한다.

```powershell
python scripts/run_friday_0918_windows_regression.py --pptx "C:\경로\20260918_금요예배(줌).pptx"
```

스크립트가 자동으로 수행하는 작업:

1. 원본 PPTX 미디어 무결성 검사
2. CRC 오류인 `media1.mp3` 제외
3. 정상 미디어 8개를 `input/friday_zoom/20260918/`에 테스트 슬롯명으로 재구성
4. 저장소의 9/18 sample weekly/Bible 자료를 `output/friday_zoom_intake/`에 준비
5. 9/18 media checklist 생성
6. `python friday.py complete 2026-09-18` 실행
7. 전체 출력을 `output/friday_0918_windows_complete.log`에 저장

실패해도 로그가 남으므로 그 파일을 기준으로 이어서 수정한다.

## 성공 시 확인

자동 단계 성공 후:

```text
FRIDAY 2026-09-18 WINDOWS REGRESSION: PASS
```

최종 파일:

```text
output/friday_zoom_20260918_final.pptx
```

PowerPoint에서 실제로 열어 다음을 수동 검수한다.

- 영상 실제 재생
- 기도 음원 실제 재생/자동 재생
- 기도 제목 애니메이션
- slide 16/17 공유 음원 동작
- 성경 본문 범위/절 번호/누락/중복
- 개역개정 및 세례→침례
- 설교 제목
- 찬양 순서
- 미디어와 화면 순서

미디어 파일이 PPT 내부에 존재하는 것과 실제 예배 환경에서 재생되는 것은 별도 검수 항목이다.

## 실제 새 주차 운영 시 Git 외부에서 필요한 것

9/18 회귀 테스트와 별개로 실제 새 주차를 제작할 때는 다음 자료가 매주 필요하다.

- 해당 주 금요기도회 안내
- 해당 주에 실제 사용할 찬양 영상/기도 음원
- Windows 환경에 아직 없다면 교회가 사용 가능한 검증된 개역개정 private Bible source/master

과거 주차 미디어나 담당 내용을 자동으로 복사하지 않는다.
