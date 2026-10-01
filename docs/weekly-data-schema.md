# Weekly Data Schema

매주 전달받는 예배 정보를 시스템 내부에서 표현하기 위한 데이터 구조를 정의한다.

이 문서는 실제 예배 자료의 디자인이나 제작 규칙을 정의하지 않는다.

세부 제작 규칙은 `AGENTS.md`를 따르며, 이 문서는 **매주 어떤 정보를 입력하고 어떤 상태로 관리할지**를 정의한다.

---

# 1. 기본 원칙

매주 예배 자료는 과거 주차의 값을 자동으로 복사하여 만들지 않는다.

해당 주에 전달된 정보만 사용한다.

동일한 항목에 여러 수정 지시가 있을 경우 `AGENTS.md`에서 정의한 우선순위를 따른다.

주일예배 PPT와 주일 주보처럼 동일한 주간 정보를 공유하는 산출물은 가능한 한 하나의 Weekly Data에서 생성한다.

같은 의미의 정보를 여러 위치에 중복 저장하지 않는다.

예를 들어 주일 2부 기도 담당자는 PPT용과 주보용으로 따로 입력하지 않고 하나의 담당자 데이터를 두 산출물이 함께 사용한다.

---

# 2. 데이터 상태

매주 변경될 수 있는 선택적 항목은 다음 세 상태 중 하나를 가진다.

## `UNSET`

아직 해당 주 정보가 전달되지 않은 상태.

예:

```yaml
special_song:
  status: UNSET
```

의미:

> 특송이 있는지 없는지 아직 모름.

`UNSET`인 값을 이전 주 자료에서 자동으로 채우지 않는다.

필수 정보가 `UNSET`이면 완성본으로 판정하지 않는다.

---

## `NONE`

해당 항목이 이번 주에는 없다고 명시된 상태.

예:

```yaml
special_song:
  status: NONE
```

의미:

> 이번 주에는 특송이 없음.

과거 주차에 특송이 있었더라도 복원하지 않는다.

---

## `VALUE`

이번 주에 사용할 값이 명시된 상태.

예:

```yaml
prayer:
  status: VALUE
  person: 홍길동
```

실제 결과물에는 `VALUE`로 확정된 값을 반영한다.

---

# 3. 공통 정보

모든 예배 Weekly Data는 기본적으로 다음 정보를 가진다.

```text
service
date
```

## `service`

예배 종류.

현재 사용할 값:

```text
wednesday
sunday
friday
```

## `date`

해당 예배 날짜.

ISO 날짜 형식 사용을 기본으로 한다.

예:

```yaml
date: 2026-10-07
```

---

# 4. 수요예배

수요예배 Weekly Data는 다음 정보를 가진다.

```text
service
date

opening_songs[3]
prayer
additional_song
scripture
sermon_title
additional_scripture
decision_hymn
```

## `opening_songs`

기본 시작 찬양 3곡.

곡마다 다음과 같은 정보를 가질 수 있다.

```text
status
title
hymn_number
verses
```

`hymn_number`와 `verses`는 해당되는 경우에만 사용한다.

---

## `prayer`

기도 담당자.

```text
status
person
```

---

## `additional_song`

기도 이후 추가 찬양.

```text
status
title
hymn_number
verses
```

---

## `scripture`

설교 본문.

```text
status
reference
```

성경 본문 텍스트 자체는 별도 성경 데이터에서 가져오며 Weekly Data에는 기본적으로 본문 범위를 기록한다.

---

## `sermon_title`

설교 제목.

```text
status
text
```

---

## `additional_scripture`

설교 중 추가로 표시할 말씀.

```text
status
reference
```

여러 본문이 필요한 구조로 확인될 경우 향후 배열로 확장할 수 있다.

---

## `decision_hymn`

결단 찬송.

```text
status
title
hymn_number
verses
```

---

# 5. 주일예배 + 주보

주일예배 PPT와 주일 주보는 별개의 Weekly Data로 관리하지 않는다.

하나의 **Sunday Weekly Data**를 기준으로 필요한 정보를 각각 사용한다.

```text
Sunday Weekly Data
        │
        ├── 주일 오전 2부 PPT
        │
        └── 주일 주보 PDF
```

Sunday Weekly Data는 다음 세 영역으로 구분한다.

```text
worship
serving
bulletin
```

각 영역의 역할:

- `worship`: 예배 순서, 찬양, 말씀 등 예배 내용
- `serving`: 이번 주와 다음 주 담당자 정보
- `bulletin`: 주보에만 필요한 상세 정보

같은 의미의 데이터를 PPT용과 주보용으로 중복 입력하지 않는다.

---

# 6. 주일 `worship`

주일예배 자체의 내용을 관리한다.

기본 구조:

```text
worship
├── opening_songs[3]
├── separate_hymn
├── offering_hymn
├── special_song
├── sermon_title
├── scripture
├── additional_scripture
└── decision_hymn
```

기도 담당자와 봉헌기도 담당자는 `worship`에 저장하지 않는다.

해당 값은 `serving.this_week.second_service`에서 가져온다.

---

## `opening_songs`

시작 찬양 3곡.

각 곡은 다음 정보를 가질 수 있다.

```text
status
title
hymn_number
verses
```

---

## `separate_hymn`

시작 찬양 이후 별도 찬송.

```text
status
title
hymn_number
verses
```

---

## `offering_hymn`

봉헌 찬송.

```text
status
title
hymn_number
verses
```

---

## `special_song`

특송.

예:

```yaml
special_song:
  status: NONE
```

`NONE`이면 해당 주에 특송 순서를 생성하지 않는다.

`UNSET`이면 특송 여부가 아직 확인되지 않은 상태로 본다.

---

## `sermon_title`

설교 제목.

```text
status
text
```

---

## `scripture`

설교 본문.

```text
status
reference
```

---

## `additional_scripture`

추가 말씀.

```text
status
reference
```

---

## `decision_hymn`

결단 찬송.

```text
status
title
hymn_number
verses
```

---

# 7. 주일 `serving`

주일 담당자 정보는 PPT와 주보가 함께 사용할 수 있도록 한 곳에서 관리한다.

기본 구조:

```text
serving
├── this_week
│   ├── first_service
│   ├── second_service
│   └── dishwashing
│
└── next_week
    ├── first_service
    ├── second_service
    └── dishwashing
```

---

## `this_week`

이번 주 담당자 정보.

예:

```yaml
serving:
  this_week:
    first_service:
      prayer:
        status: VALUE
        person: 홍길동

    second_service:
      prayer:
        status: VALUE
        person: 김철수

      offering_prayer:
        status: VALUE
        person: 이영희

    dishwashing:
      status: VALUE
      person: 박민수
```

주일 오전 2부 PPT는 다음 값을 직접 사용한다.

```text
serving.this_week.second_service.prayer
serving.this_week.second_service.offering_prayer
```

따라서 PPT용 기도 담당자를 별도로 저장하지 않는다.

---

## `next_week`

다음 주 담당자 정보.

구조는 `this_week`과 동일하게 관리할 수 있다.

전달되지 않은 담당자를 과거 순번이나 이전 주 자료로 추정하지 않는다.

예:

```yaml
serving:
  next_week:
    first_service:
      prayer:
        status: VALUE
        person: 홍길동

    second_service:
      prayer:
        status: VALUE
        person: 김철수

      offering_prayer:
        status: VALUE
        person: 이영희

    dishwashing:
      status: VALUE
      person: 박민수
```

실제 담당 항목이 더 확인되면 구조를 확장한다.

---

# 8. 주일 `bulletin`

주보에만 필요한 상세 정보를 관리한다.

기본 구조:

```text
bulletin
├── number
├── church_news
├── afternoon_service
├── monthly_schedule
└── cell_group
```

---

## `number`

주보 호수.

예:

```yaml
bulletin:
  number:
    status: VALUE
    value: "13-39"
```

제공되지 않은 경우 과거 번호를 증가시키거나 날짜만으로 계산하지 않는다.

---

## `church_news`

교회 소식.

여러 개의 공지를 배열로 관리할 수 있다.

예:

```yaml
bulletin:
  church_news:
    status: VALUE
    items:
      - text: 첫 번째 공지
      - text: 두 번째 공지
```

주일 PPT에서는 상세 공지 내용을 그대로 표시하지 않는다.

`church_news`가 있는 경우 PPT 생성기는 기본적으로 `교회 소식` 단독 안내 화면을 생성한다.

즉 하나의 데이터가 다음처럼 사용된다.

```text
church_news
    │
    ├── PPT → "교회 소식" 안내 화면
    └── 주보 → 실제 상세 공지
```

---

## `afternoon_service`

주일 오후예배 관련 정보.

예:

```yaml
bulletin:
  afternoon_service:
    status: VALUE
    title: 예시 오후예배
    description: 예시 안내
```

실제 전달 자료에서 필요한 구조가 추가로 확인되면 확장한다.

---

## `monthly_schedule`

월간 사역 일정.

기본 항목:

```text
date
content
```

예:

```yaml
bulletin:
  monthly_schedule:
    status: VALUE
    items:
      - date: 2026-10-11
        content: 예시 일정

      - date: 2026-10-18
        content: 예시 일정
```

---

## `cell_group`

목장 말씀 나누기.

기본 구조:

```text
status
scripture
title
questions[4]
```

예:

```yaml
bulletin:
  cell_group:
    status: VALUE
    scripture: "요 3:16-18"
    title: 예시 목장 말씀 제목
    questions:
      - 예시 질문 1
      - 예시 질문 2
      - 예시 질문 3
      - 예시 질문 4
```

목장 본문과 제목이 설교 본문·제목과 같아 보이더라도 자동 복사하지 않는다.

전달받은 목장 말씀 정보를 별도로 사용한다.

질문은 전달받은 원문을 사용한다.

새 질문은 사용자가 별도로 요청한 경우에만 작성한다.

---

# 9. 연도별 고정 정보

당해 연도 교회 표어처럼 매주 바뀌지 않는 값은 Weekly Data에 반복 입력하지 않는 방향을 우선한다.

예:

```text
annual_slogan
annual_slogan_subtext
```

이러한 값은 향후 별도 교회 설정 데이터로 관리할 수 있다.

예시 구조:

```yaml
yearly:
  2026:
    slogan:
      text: 확정된 2026년 교회 표어
      subtext: null
```

새 연도가 시작되면 이전 연도 값을 자동 승계하지 않는다.

해당 연도의 확정 값이 없는 경우 임의로 생성하지 않는다.

구체적인 설정 파일 위치와 저장 방식은 실제 구현 단계에서 확정한다.

---

# 10. 금요기도회

금요기도회는 `mode`에 따라 구조를 구분한다.

```text
zoom
in_person
```

금요 대면 여부는 날짜나 과거 일정에서 시스템이 추정하지 않는다.

반드시 해당 주에 전달된 값을 사용한다.

---

## 금요 공통 정보

```text
service
date
mode
```

예:

```yaml
service: friday
date: 2026-10-09
mode: zoom
```

---

# 11. 금요 Zoom

현재 확인된 기본 흐름을 기준으로 다음 데이터를 사용한다.

```text
opening_songs[2]
first_prayer
song_after_prayer

scripture
sermon_title
additional_scripture

response_song
word_prayer

intercession_song
community_prayer

personal_prayer
```

---

## `opening_songs`

예배 준비 후 시작 찬양 2곡.

금요 Zoom에서는 일반적으로 악보가 아니라 찬양 영상 자료를 사용한다.

---

## `first_prayer`

첫 기도 시간의 기도 제목.

```text
status
topics[]
```

---

## `song_after_prayer`

첫 기도 이후 찬양.

---

## `scripture`

본문 안내 및 봉독에 사용할 성경 본문.

```text
status
reference
```

---

## `sermon_title`

설교 제목.

---

## `additional_scripture`

추가 말씀.

---

## `response_song`

말씀 이후 응답 찬양.

---

## `word_prayer`

말씀과 관련된 기도 제목.

```text
status
topics[]
```

---

## `intercession_song`

공동체·중보기도 전후에 사용하는 찬양.

---

## `community_prayer`

공동체 및 중보기도 제목.

```text
status
topics[]
```

---

## `personal_prayer`

개인 기도 순서.

필요한 별도 문구가 있는 경우 추후 구조를 확장한다.

---

# 12. 금요 미디어 데이터

금요 Zoom 찬양의 영상·음원은 단순히 파일 경로만으로 관리하지 않는다.

향후 다음 상태를 구분할 수 있도록 설계한다.

```text
파일 확보 여부
기술 검수 여부
교회 검수 여부
사용 허락 / 저작권 확인 여부
```

예시 개념:

```yaml
media:
  status: VALUE

  file_status: AVAILABLE

  technical_check: VERIFIED
  church_review: VERIFIED
  usage_permission: UNKNOWN
```

세부 enum과 저장 방식은 실제 금요 Zoom 구현 단계에서 확정한다.

기존 확인 자료에 MP4 5개와 MP3 4개가 있었다는 사실은 참고 사례이며 모든 금요 Zoom의 고정 개수로 사용하지 않는다.

---

# 13. 금요 대면

금요 대면은 Zoom의 영상 자료를 악보로 교체하는 구조로 간주하지 않는다.

찬양 수, 기도 배치, 전체 순서가 다를 수 있다.

따라서 현재 Weekly Data에서는 다음까지만 확정한다.

```text
service
date
mode: in_person
```

세부 필드는 검수된 금요 대면 자료의 구조를 다시 분석한 후 확정한다.

확인되지 않은 구조를 현재 단계에서 임의로 만들지 않는다.

---

# 14. 예시 파일

Weekly Data 구조 확인을 위해 실제 교회 자료와 분리된 예시 데이터를 관리한다.

```text
samples/
└── weekly/
    ├── wednesday.example.yaml
    ├── sunday.example.yaml
    └── friday-zoom.example.yaml
```

예시 데이터는 실제 해당 주 예배 정보로 간주하지 않는다.

개인정보나 실제 민감한 교회 자료를 예시 파일에 넣지 않는다.

---

# 15. 향후 확장

현재 스키마는 POC를 통해 확인된 구조를 기준으로 한다.

실제 구현 과정에서 다음이 필요하면 확장할 수 있다.

- 복수 추가 말씀
- 찬양별 절/후렴 정보
- 찬양 라이브러리 참조 ID
- 추가 주일 섬김 항목
- 미디어 검수 상태
- 원본 자료 참조 정보
- 입력 출처
- 수정 이력

단, 실제 자료에서 확인되지 않은 필드를 필요 이상으로 미리 설계하지 않는다.

스키마 변경이 교회 제작 규칙에 영향을 줄 경우 `AGENTS.md`를 우선 확인한다.