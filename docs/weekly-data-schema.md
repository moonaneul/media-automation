# Weekly Data Schema

매주 전달받는 예배 정보를 시스템 내부에서 표현하기 위한 데이터 구조.

## 상태

모든 선택적 주간 항목은 다음 세 상태를 가진다.

- UNSET: 아직 전달되지 않음
- NONE: 이번 주에는 없음
- VALUE: 사용할 값이 전달됨

UNSET과 NONE을 같은 값으로 처리하지 않는다.

## 공통 정보

- service
- date

## 수요예배

- opening_songs[3]
- prayer
- additional_song
- scripture
- sermon_title
- additional_scripture
- decision_hymn

## 주일예배

- opening_songs[3]
- separate_hymn
- prayer
- church_news
- offering_hymn
- offering_prayer
- special_song
- sermon_title
- scripture
- additional_scripture
- decision_hymn

## 주보

- bulletin_number
- annual_slogan
- afternoon_service
- this_week_service
- next_week_service
- church_news
- monthly_schedule
- cell_group