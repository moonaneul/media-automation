# Media Automation — 교회 예배 미디어 제작 자동화

> **매주 반복되지만, 매번 내용과 형식이 다른 예배 자료 제작을 안전한 작업 흐름으로 바꾸는 프로젝트**
>
> 실제 하늘빛기쁨성서침례교회 미디어팀 업무를 출발점으로, **예배 안내 입력 → 주간 데이터 정리 → 자료 등록 → PPT/주보 제작 → 검수 → 전달** 과정을 설계하고 구현하고 있습니다.

**현재 상태 (2026-10-15 기준): 로컬에서 제작·검증한 사례가 있으며 웹 기반 작업 도구를 통합한 단계. 공용 인터넷 서비스 배포는 미완료.**

> **운영 전환 참고:** [Cloud Run·Supabase 시험과 제한 사항](docs/hosted_runtime_20261014.md)은 [Draft PR #14](https://github.com/moonaneul/media-automation/pull/14)에, 최근 UI·OneDrive 변경은 [Draft PR #15](https://github.com/moonaneul/media-automation/pull/15)에 보관 중입니다. 두 PR의 시험 결과가 정식 공동 운영 검증을 뜻하지는 않습니다. 기존 로컬 실행 방식과 DB 보존 규칙은 [로컬 통합 기록](docs/local_consolidation_20261013.md)을 참고하세요. 코드의 구현 여부, 테스트 통과, 실제 예배 환경에서의 사용 가능성은 서로 다른 상태로 관리합니다.

| 한눈에 보기 | 내용 |
| --- | --- |
| 풀고자 한 문제 | 반복 수작업, 주별 입력 누락·과거 내용 잔존, 서로 다른 예배 형식, 수동 콘텐츠 교차검수 |
| 실제 사용자 | 교회 미디어팀, 예배 정보를 전달하는 담당자 |
| 결과물 | 수요·주일예배 PPTX, 금요 Zoom PPTX, 인쇄용 주보 PDF, 로컬 웹 작업 화면 |
| 핵심 기술 | Python, Pydantic, PyYAML, python-pptx, ReportLab, PyMuPDF, SQLite, HTML/CSS/JavaScript, Microsoft PowerPoint 연동 |
| 핵심 설계 | 주간 입력의 3상태 모델, 블록 기반 조립, 예배별 정책, 원본 보존, 생성/검수 상태 분리 |
| 운영 현황 | Mac/Windows 기반 제작 검증 및 로컬 브라우저 사용 확인. Linux·공용 서버 이전과 실제 온라인 배포는 후속 과제 |

## 1. 시작한 이유 — 실제 업무에서 발견한 문제

교회 미디어팀은 매주 수요예배, 금요기도회, 주일예배 PPT와 주일 주보를 준비합니다. 필요한 정보는 담당자가 보낸 안내 문장, 전달 주보(HWP), 악보 PPT, 성경 본문, 영상·음원처럼 여러 형식으로 들어옵니다. 예배마다 디자인과 순서도 다릅니다.

기존에는 과거 PPT를 수정하며 이번 주 내용을 채워 넣는 과정에서 **누락된 정보를 지난주 값으로 남겨두기 쉽고**, 주일 PPT와 주보의 설교 제목이나 담당자가 달라질 여지가 있었습니다. 파일이 만들어져도 악보 잘림이나 영상 재생 문제가 없다고 단정할 수 없었습니다.

그래서 목표를 단순한 'PPT 자동 생성기'로 정하지 않았습니다.

**“정보를 제공하는 사람은 이번 주 내용을 전달하고, 시스템은 정해진 규칙대로 준비하며, 미디어팀은 최종 검수와 실제 예배 운영에 집중한다.”**

이 프로젝트는 연습용 가상 서비스가 아니라 **반복되는 실제 제작 업무를 개선하면서 요구사항과 검증 기준을 다듬어 온 프로젝트**입니다. 모든 예배와 모든 환경에서 무인 자동화가 완성됐다는 뜻은 아닙니다.

## 2. 무엇을 만들었나

| 제작 범위 | 입력과 특징 | 구현·검증의 중심 |
| --- | --- | --- |
| **수요예배 (약 4:3)** | 안내 문장, 악보 PPT, 개역개정 본문 | 찬양·기도·말씀 블록 조립, 절별 슬라이드, 순서 경계 빈 화면, 원본 악보 재사용 |
| **주일예배 2부 (약 4:3)** | 예배 안내, 담당자, 찬양 원본, 말씀 | 예배 순서별 조립과 주보 공통 정보 연계 |
| **금요기도회 Zoom (16:9)** | 기도 순서, 본문, 찬양 영상, 기도 음원 | 영상·음원 포함 PPT, 기도 화면 및 순서 처리, 별도 미디어 검증 |
| **주일 주보 (A4 가로 양면 PDF)** | 전달 주보 HWP/HWPX/TXT, 주일 공통 데이터, 확인된 호수 | 논리 4쪽을 실제 인쇄용 PDF 2면으로 구성하고 한글 폰트·여백·배치 확인 |
| **웹 작업 화면** | 주차별 정보, 파일·원본 선택, 검토 및 생성 요청 | 로컬 입력 저장, 주차 관리, 자료 연결, 제작·다운로드 흐름 통합 |

금요 **대면** 예배는 Zoom의 영상만 악보로 바꾸는 방식으로 처리하지 않습니다. 다른 순서·배치가 필요하므로 현재 구현·검증 범위를 구분합니다.

### 제작 흐름

~~~mermaid
flowchart LR
  A["해당 주 예배 안내<br/>전달 주보·수정 지시"] --> B["입력 파싱 및 검토"]
  B --> C["주간 데이터<br/>UNSET / NONE / VALUE"]
  D["검수된 악보·템플릿<br/>허용된 성경·미디어"] --> E["예배별 제작 엔진"]
  C --> E
  E --> F["PPTX / 주보 PDF"]
  F --> G["자동 구조 점검"]
  G --> H["사람의 화면·인쇄·재생 검수"]
  H --> I["예배 사용·전달"]
~~~

**자동 생성 성공 ≠ 최종 검수 통과 ≠ 온라인 배포 완료**라는 구분이 프로젝트 전반의 원칙입니다.

## 3. 가장 중요한 설계 판단

### ① 입력값을 세 상태로 나누기

이번 주 담당자·본문·찬양이 전달되지 않았는데 지난주 데이터를 복사하면 화면은 그럴듯해 보여도 실제 내용은 틀릴 수 있습니다. 그래서 입력을 단순 빈 문자열이 아니라 다음처럼 구분합니다.

| 상태 | 의미 | 처리 |
| --- | --- | --- |
| **UNSET** | 아직 정보가 전달되지 않음 | 필수 항목이면 제작을 멈추고 확인 요청 |
| **NONE** | 이번 주에는 해당 항목이 없다고 명시됨 | 다른 주 자료로 채우지 않음 |
| **VALUE** | 사용할 내용이 명시됨 | 최신 명시적 수정 지시까지 확인 후 반영 |

같은 주의 수정 사항은 누적하되, 변경되지 않은 나머지 항목은 유지합니다. 애매한 입력은 임의 확정하지 않습니다. 이 원칙은 파일 자동 생성보다 **잘못된 내용이 실제 예배 화면에 나가지 않게 하는 것**을 우선한 결정입니다.

관련 코드: [주간 데이터 모델](src/media_automation/weekly_data/models.py) · [데이터 스키마](docs/weekly-data-schema.md) · [작업 규칙](AGENTS.md)

### ② 이전 PPT 전체 복사가 아닌 블록 조립

곡마다 악보 페이지 수가 다르고 성경 본문 길이도 매주 다릅니다. 슬라이드 수를 고정하거나 지난주 PPT를 통째로 복사하는 대신, **예배 전 안내 / 찬양 원본 / 빈 화면 / 기도 / 말씀 / 제목** 등 블록을 서비스별 정책에 맞게 조립합니다.

- 수요·주일은 기본적으로 성경 **한 절당 한 화면**을 사용합니다.
- 주요 **예배 순서가 바뀌는 경계**에 빈 슬라이드를 넣습니다.
- 원본 악보 PPT의 디자인을 임의로 가사 화면으로 바꾸지 않습니다.
- 필요한 악보를 확보하지 못하면 비슷한 곡으로 조용히 대체하지 않습니다.
- 금요 Zoom의 영상·음원 배치와 금요 대면의 구성을 구분합니다.

관련 코드: [블록 계획](src/media_automation/planning/planner.py) · [PPT 조립](src/media_automation/ppt/slide_merge.py)

### ③ 주일 PPT와 주보의 공통 정보 연결

처음에는 두 결과물을 각각 만드는 방식이었지만, 같은 주에 공통으로 등장하는 설교 본문·제목·담당자·광고가 서로 불일치할 수 있었습니다.

이후 **전달 주보를 한 번 등록**하고, 주일 안내와 공통 데이터를 대조하도록 연결했습니다. 날짜가 다르거나 정보가 충돌할 때 자동 덮어쓰지 않고 멈추며, 주보 호수도 과거 호수에서 추정하지 않도록 변경했습니다.

인쇄 결과는 A4 가로 **[4쪽 | 1쪽] / [2쪽 | 3쪽]**의 2면 PDF입니다.

근거: [PR #8 — PPT·주보 원본 공유와 교차검수](https://github.com/moonaneul/media-automation/pull/8) · [주보 화면 검수](docs/bulletin_20260927_review.md)

### ④ 파일의 존재와 실제 사용 가능성을 분리

이 시스템에서 'PPT 파일을 생성했다'는 말은 '예배에서 문제없이 재생된다'는 뜻이 아닙니다.

- 텍스트·슬라이드 구조·링크·본문 범위는 코드로 점검할 수 있는 부분을 자동화합니다.
- 이미지에 들어 있는 악보·성경 텍스트, 화면 잘림과 가독성은 실제 렌더링을 봐야 합니다.
- PPT 내부에 MP4/MP3가 존재하는 것과 PowerPoint에서 재생되는 것은 별개입니다.
- 자료를 **보유**하는 것과 사용 **허락**을 받은 것도 별개입니다.

따라서 생성, 자동 QA, 실제 화면, 재생, 실물 인쇄와 접지를 각각 확인하도록 설계했습니다.

관련 코드: [독립 QA](src/media_automation/qa/inspection.py) · [예배 PPT 검수](src/media_automation/ppt/in_person_qa.py) · [웹 아키텍처와 제한](docs/webapp_architecture.md)

## 4. 개발 과정과 시행착오

| 문제 / 관찰 | 시도 또는 원인 | 바꾼 방식과 배운 점 | 근거 |
| --- | --- | --- | --- |
| 이전 주 데이터가 새 주에 남을 위험 | 과거 PPT 재활용·불완전한 입력값 | UNSET/NONE/VALUE로 명확히 구분하고 필수 정보 미확정 시 생성 차단 | [PR #1](https://github.com/moonaneul/media-automation/pull/1) |
| 오래된 악보 원본과 불필요한 클릭 링크 | .ppt 원본 변환, 악보 슬라이드 병합 시 외부 링크 유입 | 원본은 보존하면서 PPTX로 변환·슬롯 등록; 최종 병합 시 링크 제거와 구조 QA | [PR #6](https://github.com/moonaneul/media-automation/pull/6) · [PR #7](https://github.com/moonaneul/media-automation/pull/7) |
| 주보 호수 자동 계산의 위험 | 날짜에서 호수를 +1/-1 추론하는 접근을 시도 | 이후 최신 업무 규칙에 맞춰 **명시적으로 확인된 호수만 사용**하도록 변경 | [PR #4](https://github.com/moonaneul/media-automation/pull/4) → [PR #8](https://github.com/moonaneul/media-automation/pull/8) |
| PDF에서 한글이 깨지거나 누락 | 환경에 따라 글꼴이 달라지고 폰트가 포함되지 않음 | 한글 TTF 임베딩 및 렌더링 검사, 필요한 글꼴이 없으면 오류 처리 | [주보 검수 기록](docs/bulletin_20260927_review.md) |
| 금요 영상·음원 파일이 들어 있는데도 재생/무결성 문제 | 과거 Zoom PPT의 일부 MP3에서 CRC 오류 발견 | ZIP 내부 무결성 점검, 손상 음원 제외, 역할별 음원 연결 및 PowerPoint 실제 재생 검수 분리 | [금요 Windows 인수인계](docs/friday_zoom_windows_handoff.md) · [PR #5](https://github.com/moonaneul/media-automation/pull/5) |
| 서로 다른 브랜치와 로컬 작업본에 기능 분산 | 화면·제작 API·주간 입력 처리 구현이 서로 다른 코드 기준에 존재 | 기존 코드와 입력 자료를 구분하고 코드 중심으로 병합; 회귀 테스트 및 읽기 전용 차이 조사 추가 | [PR #10](https://github.com/moonaneul/media-automation/pull/10) · [PR #11](https://github.com/moonaneul/media-automation/pull/11) · [PR #13](https://github.com/moonaneul/media-automation/pull/13) |
| 생성 오류가 사용자에게 잘 보이지 않음 | 제작기 예외와 웹 다운로드 결과가 분리됨 | 원인 표시, 부분 제작 상태, 실제 결과 형식에 맞춘 다운로드 처리 | [PR #11](https://github.com/moonaneul/media-automation/pull/11) |
| 무료 웹 서버로 옮기기 어려움 | 대용량 미디어 PPT의 메모리·CPU·디스크 요구 | 먼저 Mac에서 계측한 뒤 Linux·무료 서버 후보와 선행 조건 비교. **외부 배포 완료로 간주하지 않음** | [온라인 운영 검토](src/media_automation/_legacy_migration/review-docs/online-operating-plan.md) |

특히 **한 번 구현한 기능도 실제 운영 원칙과 어긋나면 되돌리거나 제한**했습니다. 예를 들어 주보 호수를 자동 계산하는 기능은 기술적으로 구현할 수 있어도 실제 정확성을 보장하지 못해 명시적 입력으로 회귀했습니다.

## 5. 구현과 검증에서 확인한 결과

아래 숫자는 **특정 시점·특정 주차의 기록**입니다. 전체 주차의 보편적 성공률, 제작 시간 절감률, 상시 서비스 가동률을 의미하지 않습니다.

| 검증 사례 | 확인된 기록 | 해석 |
| --- | --- | --- |
| 수요 2026-09-30 | 68장 PPT 생성, 원본 유입 링크 286개 제거, 최종 QA 및 PowerPoint 화면 확인 기록 | 안내→악보→본문→합성→점검의 실제 사례 |
| 수요 2026-10-07 | 74장 생성, 링크 520개 제거, 구조 QA 통과 기록 | 고정 장수가 아닌 예배별 조립 검증. 환경별 실제 화면 검수는 별도 |
| 주일 2026-09-27 | 67장 PPT 생성과 Microsoft PowerPoint 열기 검증 기록 | 실주차 악보 슬롯 등록·본문·조립 확인 |
| 주보 2026-09-27 | A4 가로 PDF 2면 생성, 렌더링과 한글 글꼴 임베딩 확인 | **실제 양면 출력·접지는 미검증** |
| 금요 Zoom 2026-09-18 | E2E 제작 및 PowerPoint 재생 확인 기록 | 파일 내장뿐 아니라 실제 실행 확인이 필요함을 반영 |
| 금요 별도 제작 측정 (2026-10-10, macOS) | **35장, 약 269MB, 약 21.8초**, 부모 프로세스 최대 RSS 약 930MB | Linux 배포를 위한 용량 추정의 근거. Linux 성능 수치 아님 |
| 통합 작업본 (2026-10-13) | 비공개 테스트용 자산을 별도로 설치한 환경에서 **657 tests passed, 2 skipped** 기록 | 해당 시점 통합 검증 수치. 현재 모든 환경의 최종 E2E 보증은 아님 |

근거: [수요 PR #1](https://github.com/moonaneul/media-automation/pull/1) · [수요 PR #6](https://github.com/moonaneul/media-automation/pull/6) · [주일 PR #7](https://github.com/moonaneul/media-automation/pull/7) · [금요 PR #5](https://github.com/moonaneul/media-automation/pull/5) · [10/13 통합 기록](docs/current_8873_integration_20261013.md) · [데스크톱 웹앱 인수인계](docs/desktop_webapp_handoff_20261010.md)

**검증에서 중요하게 생각한 질문:** “코드가 실행됐는가?”뿐 아니라 “이번 주에 의도한 예배 순서와 텍스트가 맞는가?”, “결과 파일에 위험한 잔존 요소가 없는가?”, “실제로 볼 때와 재생할 때 정상인가?”를 분리했습니다.

## 6. 기술과 코드 구조

### 기술 스택

| 영역 | 실제 저장소에서 사용하는 도구 |
| --- | --- |
| 언어·런타임 | Python 3.11+, 브라우저 JavaScript |
| 데이터·검증 | Pydantic, PyYAML, JSON, SQLite |
| PPT 생성 | python-pptx, Open XML 조립, Microsoft PowerPoint 환경별 변환/재생 검수, Windows용 pywin32 |
| 주보·파일 | ReportLab, Pillow, PyMuPDF, pypdf, olefile |
| 미디어·외부 자료 | imageio-ffmpeg, requests, MSAL, cryptography; OneDrive 연동 코드는 존재하나 실제 원격 운영 검증은 별도 |
| 웹 | HTML/CSS/JavaScript, Python 표준 라이브러리 기반 HTTP 서버, 로컬 작업 DB |
| 테스트·협업 | pytest, Git/GitHub, PR 및 회귀 테스트 |

### 주요 구성

~~~text
webapp.py                 # 현재 기본 웹 진입점
src/media_automation/
  web/original/           # 현재 웹app에서 사용하는 원본형 작업 화면·API·저장소
  web/                    # 별도 제작 작업 API, 입력·검수·미리보기 구현
  weekly_data/            # 주간 입력 3상태 모델, 검증
  planning/               # 예배별 블록·순서 계획
  bible/                  # 승인된 개역개정 원문 조회·검증 경계
  ppt/                    # 예배 PPT 조립, 악보·미디어·구조 QA
  bulletin/               # 전달 주보 처리, 인쇄용 PDF
  production/             # 작업별 분리 실행과 결과 추적
  qa/                     # 독립 구조 점검
wednesday.py / sunday.py / friday.py / bulletin.py
scripts/                  # 개별 제작·자료 등록·진단 스크립트
tests/                    # 회귀·통합 테스트
docs/                     # 설계 결정, 검수 기록, 인수인계
experiments/              # 이관 검토/과거 실험 스냅샷 (현재 진입점과 구분)
~~~

> **구현 주의:** 웹 코드에는 원본형 화면과 별도의 제작 작업 API가 함께 보존돼 있습니다. 현재 <code>webapp.py</code> 기본 실행은 <code>web/server.py</code>를 통해 **<code>web/original/</code> 화면**으로 연결됩니다. 모든 실험 코드가 동일한 운영 경로로 통합됐다는 의미는 아닙니다.

## 7. 로컬에서 실행하기

저장소 코드만으로 교회 실자료가 자동 포함되지는 않습니다. 다음 절차는 **개발 환경과 화면 확인**용이며, 실제 PPT/PDF 제작에는 서비스별로 검수된 원본·성경 자료·글꼴·미디어와 적합한 Office 환경이 별도로 필요합니다.

**요구 환경:** Python 3.11+, Git. 실제 변환·재생은 운영체제 및 Microsoft PowerPoint/LibreOffice 환경을 따릅니다.

~~~bash
git clone https://github.com/moonaneul/media-automation.git
cd media-automation

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'

# 코드 테스트: 일부는 별도의 비공개 글꼴/원본 자산이 필요할 수 있음
python -m pytest -q

# 기존 운영 DB와 섞이지 않는 별도 시험용 DB 사용
python webapp.py --port 18769 --database /tmp/media-automation-readme-demo.sqlite
~~~

브라우저에서 **http://127.0.0.1:18769/** 을 엽니다. 테스트를 마쳤다면 실행 터미널에서 Ctrl+C로 종료합니다. Windows에서는 가상환경 활성화·임시 파일 경로를 해당 OS에 맞게 바꿉니다.

서비스별 명령 확인:

~~~bash
python wednesday.py --help
python sunday.py --help
python friday.py --help
python bulletin.py --help

# 구조 검수 도구 사용법
python -m media_automation.qa --help
~~~

실제 제작 단계는 [수요 운영 절차](docs/wednesday_workflow.md) · [금요 Zoom 절차](docs/friday_zoom_workflow.md) · [주일 악보 등록](docs/sunday_song_registration.md) · [웹 구조](docs/webapp_architecture.md)를 참고하세요. 예시 날짜나 샘플 담당자를 실제 이번 주 값으로 자동 사용하지 않습니다.

## 8. 로컬 운영에서 외부 배포까지

| 단계 | 현재 확인한 상태 |
| --- | --- |
| 1. 예배별 수동 업무·템플릿 분석 | 완료된 POC 및 실주차 검수 기록 존재 |
| 2. Python 제작 엔진·웹 입력 화면 구축 | 구현 및 부분 통합, 로컬 제작·화면·회귀검증 기록 존재 |
| 3. Mac 로컬 사용 / 모바일 핫스팟 접속 시험 | 사용자 확인 기록 존재 ([인수인계](docs/desktop_webapp_handoff_20261010.md)) |
| 4. Linux 이전 가능성·무료 서버 자원 조사 | **사전 검토 단계**. 대용량 PPT 측정 및 배포 조건 점검 코드 작성 |
| 5. 무료 서버 인스턴스 확보, HTTPS·인증·백업, OneDrive 실연결 | **완료 확인 없음** |
| 6. 팀원 외부 접속, 서버 생성·PowerPoint 재생·양면 인쇄까지 인수검수 | **미완료** |

현재 GitHub 저장소는 **코드 공개와 협업 공간**이며, 예배 제작 서비스를 호스팅하는 주소가 아닙니다. <code>media.hjbbc.or.kr</code>은 논의한 후보 도메인일 뿐 개통되었다고 주장하지 않습니다. 무료 서버 후보(Oracle Always Free 등)도 검토 단계입니다.

서버 이전에서는 특히 macOS/Windows에서 동작한 PowerPoint 의존 흐름을 Linux에서도 재현할 수 있는지, 큰 MP4 포함 PPT를 안전하게 처리할 메모리·디스크가 충분한지, **외부 접속 전에 HTTPS·인증·접근 제어·백업**을 완료했는지를 따로 확인해야 합니다.

참고: [온라인 운영 검토](src/media_automation/_legacy_migration/review-docs/online-operating-plan.md) · [배포 사전 점검 코드](src/media_automation/web/deployment_check.py)

## 9. 프로젝트에서 맡은 일과 얻은 관점

실제 미디어 제작 경험을 바탕으로 **문제를 정의하고 요구사항과 검수 기준을 구체화하는 역할**을 수행했습니다. 예배별로 무엇이 다른지 사례를 정리하고, 전달 지시의 우선순위, 자동화해도 되는 부분과 사람이 검수해야 하는 부분, 입력 UI에서 혼동되는 부분을 반복적으로 검토했습니다. 구현 및 수정 과정에서는 AI 개발 도구를 활용하면서 결과 코드·실행 흐름을 확인하고 피드백을 반영하는 방식으로 진행했습니다.

이 과정에서 얻은 핵심 교훈은 다음과 같습니다.

1. **자동화의 성공은 생성 속도만이 아니다.** 잘못된 자료를 그럴듯하게 생성하지 않도록 '멈출 조건'을 설계하는 일이 더 중요할 수 있다.
2. **실제 사용자는 기능 목록보다 작업 흐름을 기준으로 판단한다.** 코드와 웹 화면을 만들고도 파일·브랜치·입력이 분산돼 있다면 운영이 어렵다.
3. **검증은 계층별로 나눠야 한다.** 테스트 통과, PPT 내용 정확성, 기기별 재생, 실제 인쇄, 공개 서비스 보안은 서로 다른 검증이다.
4. **제약이 설계를 바꾼다.** 무료 서버 조건, 269MB급 결과물, 글꼴·Office 의존성, 개인정보와 콘텐츠 사용권은 기능 구현만으로 해결되지 않는다.

이는 금융·공공 등 **정확한 데이터 처리, 업무 절차의 신뢰성, 사용자 중심 설계, 운영 전 검증**이 중요한 직무에서도 설명할 수 있는 경험입니다. 다만 산업별 실서비스 운영 성과가 이미 확보됐다는 주장과는 구분합니다.

## 10. 다음 목표

- **실제 주간 제작을 반복 검증:** 수요·주일·금요 Zoom·주보의 입력부터 최종 화면/재생/인쇄까지 같은 기준으로 기록
- **데이터·자산 흐름 단순화:** 로컬 작업본, 원본 자료, 코드, 결과물의 책임과 위치를 정리하고 불필요한 복제 최소화
- **공통 정보 검수 강화:** 같은 주 PPT·주보의 본문, 제목, 담당자, 광고를 생성 전후 교차검증
- **서버 준비 검증:** Linux 제작 가능성, 대용량 파일, 영구 저장소, HTTPS·인증, 백업/복구와 무료 운영 범위 확인
- **원격 자료 처리 검증:** OneDrive 권한 동의, 원본 무결성, 파일 보관 성공 여부 및 저작권 상태의 구분
- **배포 및 인수검수:** 외부 접속 가능 여부만이 아닌 실제 사용자가 안전하게 전체 제작을 마칠 수 있는지 확인

프로젝트 방향이나 우선순위는 실제 미디어팀의 요구에 따라 바뀔 수 있습니다. **확인되지 않은 마감일과 정량 성과는 적지 않습니다.**

---

### 더 알아보기

- [제작에서 가장 중요한 공통 규칙 — AGENTS.md](AGENTS.md)
- [업무 프로세스와 상태 설계 — weekly-data-schema.md](docs/weekly-data-schema.md)
- [웹앱 구조·실행·검증 범위 — webapp_architecture.md](docs/webapp_architecture.md)
- [2026-10-13 코드 통합과 QA 기록](docs/current_8873_integration_20261013.md)
- [주요 PR과 변경 이유](https://github.com/moonaneul/media-automation/pulls?q=is%3Apr)
- [README를 재검토·갱신하는 프롬프트](docs/README_WRITING_PROMPT.md)

> 이 공개 저장소의 목적은 **코드·설계·검수 과정 공유**입니다. 실제 교회 연락처·담당자 정보가 들어 있는 주간 입력, 성경 원문 전체, 악보 원본, 영상·음원, 비밀키, 제작 결과물의 공개 또는 재배포 허락을 의미하지 않습니다.
