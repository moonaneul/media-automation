# 금요기도회 Zoom PPT 제작

금요 Zoom PPT는 friday.py 하나로 작업한다.

## 1. 이번 주 시작

python friday.py start "이번주안내.txt"

이 단계에서 자동으로 확인한다:
- 날짜
- 찬양
- 기도 제목
- 성경 본문
- 설교 제목
- 추가 말씀
- 응답 찬양
- Bible 요청
- 미디어 체크리스트

지난주 내용이나 과거 미디어는 자동으로 가져오지 않는다.

## 2. 현재 상태 확인

python friday.py status YYYY-MM-DD

예:
python friday.py status 2026-10-09

## 3. REVIEW가 발생한 경우

확인이 필요한 문장 보기:

python friday.py review YYYY-MM-DD

예배 자료와 관계없는 문장이라면:

python friday.py ignore YYYY-MM-DD "무시할 문장"

특정 항목으로 넣어야 한다면:

python friday.py assign YYYY-MM-DD FIELD "문장"

검토가 끝나면:

python friday.py resume YYYY-MM-DD

## 4. 미디어 준비

이번 주 폴더:

input/friday_zoom/YYYYMMDD/

필수 파일:

- opening_song_1.mp4
- opening_song_2.mp4
- first_prayer.mp3
- song_after_prayer.mp4
- response_song.mp4
- word_prayer.mp3
- intercession_song.mp4
- community_prayer.mp3
- personal_prayer.mp3

선택:

- pre_service_audio.mp3

비슷한 파일명이나 과거 주차 미디어를 자동 대체하지 않는다.

## 5. 최종 PPT 제작

python friday.py complete YYYY-MM-DD

## 가장 자주 쓰는 흐름

정상 주간:

start -> media -> complete

REVIEW가 있는 주간:

start -> review 처리 -> resume -> media -> complete

## 최종 수동 검수

- 영상 실제 재생
- 음원 자동 재생
- 기도 제목 애니메이션
- 성경 본문 범위와 절 번호
- 본문 누락/중복
- 개역개정 확인
- 세례 -> 침례 확인
- 설교 제목
- 찬양 순서
- 미디어와 화면 순서 일치

미디어 파일이 PPT 안에 존재하는 것과 실제 예배 환경에서 정상 재생되는 것은 별도 검수한다.

## 핵심 원칙

- 과거 주차 내용을 자동 승계하지 않는다.
- 빈 항목과 미제공 항목을 구분한다.
- 성경 본문을 임의 생성하지 않는다.
- 개역개정을 사용한다.
- 미디어를 임의 추정하거나 과거 파일로 대체하지 않는다.
