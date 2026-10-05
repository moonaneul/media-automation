from media_automation.bulletin import (
    parse_bulletin_transfer_text,
)
from media_automation.weekly_data.models import (
    WeeklyStatus,
)


TRANSFER_20260927 = """
주보  하늘빛기쁨교회

9/27

cf) 오후 예배 : 생명의 삶 3주차

찬양 : 337, 430장, 주님 말씀하시면

*설교 중 읽을 말씀 ☞

<교회 소식>
1. 오늘 오후 시간은 ‘생명의 삶’ 3주 차입니다.
2. 새 가족반 공부가 12시 45분에 목양실에서 있습니다.
3. 지저스 미션 컨퍼런스: 10/9~10, 성서침례대학원대학교, 사전 접수 요망

<9월 사역 일정>
9/6(일) : 집사 부부 모임
9/13(일) : 교회 청소, 생명의 삶 개강
9/14(월) : 서울지역 목회자 친교회(하늘빛기쁨교회)
9/24(목)~26(토) : 추석 연휴

<목장 말씀 나누기>

<히 11:1~3 / 살아 있는 믿음>

1. 여러분은 "보이지 않는 것을 보는 것처럼 행동하는 믿음"을 실제 삶에서 경험한 적이 있나요?
2. 응답받기 전에 받은 줄로 믿는 신앙은 어떤 모습일까요? 우리 삶에 어떻게 적용할 수 있을까요?
3. 말씀을 따라 행동하는 믿음과 단순히 입술로만 고백하는 믿음의 차이는 무엇이라고 생각하나요?
4. 오늘날 교회와 성도들이 믿음을 잃어버리게 만드는 가장 큰 요인은 무엇이라고 생각하나요?
"""


def test_parse_20260927_bulletin_transfer():
    result = parse_bulletin_transfer_text(
        TRANSFER_20260927,
        year=2026,
    )

    assert result.date.isoformat() == (
        "2026-09-27"
    )

    assert (
        result.afternoon_service.status
        == WeeklyStatus.VALUE
    )
    assert (
        result.afternoon_service.value
        == "생명의 삶 3주차"
    )

    assert (
        result.praise_raw.status
        == WeeklyStatus.VALUE
    )
    assert (
        result.praise_raw.value
        == "337, 430장, 주님 말씀하시면"
    )

    # 항목은 있지만 값이 비어 있으므로 NONE
    assert (
        result.additional_scripture.status
        == WeeklyStatus.NONE
    )

    assert (
        result.church_news.status
        == WeeklyStatus.VALUE
    )
    assert len(
        result.church_news.items
    ) == 3

    assert (
        result.monthly_schedule.status
        == WeeklyStatus.VALUE
    )
    assert len(
        result.monthly_schedule.items
    ) == 4

    assert (
        result.cell_group.status
        == WeeklyStatus.VALUE
    )
    assert (
        result.cell_group.scripture
        == "히 11:1~3"
    )
    assert (
        result.cell_group.title
        == "살아 있는 믿음"
    )
    assert len(
        result.cell_group.questions
    ) == 4


def test_missing_transfer_item_is_unset():
    result = parse_bulletin_transfer_text(
        "9/27",
        year=2026,
    )

    assert (
        result.afternoon_service.status
        == WeeklyStatus.UNSET
    )
    assert (
        result.praise_raw.status
        == WeeklyStatus.UNSET
    )
    assert (
        result.additional_scripture.status
        == WeeklyStatus.UNSET
    )

SERVING_20260927 = """
9/27

*예배 / 섬김 :

구 분
기 도
봉 헌 기 도
설 거 지
수요예배 기도

이 번 주

1 부
인도자
이광민
이하선, 문바다
한송희

2 부
위윤기
문호성

다 음 주

1 부
인도자
김진아
한윤선, 이광민
한미선

2 부
문희재
장기훈

*1면 –
"""


def test_parse_20260927_serving_table():
    result = parse_bulletin_transfer_text(
        SERVING_20260927,
        year=2026,
    )

    serving = result.serving

    assert (
        serving.status
        == WeeklyStatus.VALUE
    )

    this_week = serving.this_week
    assert this_week is not None

    assert (
        this_week.first_service_prayer
        == "인도자"
    )
    assert (
        this_week.first_service_offering_prayer
        == "이광민"
    )
    assert (
        this_week.second_service_prayer
        == "위윤기"
    )
    assert (
        this_week.second_service_offering_prayer
        == "문호성"
    )
    assert (
        this_week.dishwashing
        == "이하선, 문바다"
    )
    assert (
        this_week.wednesday_prayer
        == "한송희"
    )

    next_week = serving.next_week
    assert next_week is not None

    assert (
        next_week.first_service_prayer
        == "인도자"
    )
    assert (
        next_week.first_service_offering_prayer
        == "김진아"
    )
    assert (
        next_week.second_service_prayer
        == "문희재"
    )
    assert (
        next_week.second_service_offering_prayer
        == "장기훈"
    )
    assert (
        next_week.dishwashing
        == "한윤선, 이광민"
    )
    assert (
        next_week.wednesday_prayer
        == "한미선"
    )


def test_missing_serving_table_is_unset():
    result = parse_bulletin_transfer_text(
        "9/27",
        year=2026,
    )

    assert (
        result.serving.status
        == WeeklyStatus.UNSET
    )



def test_schedule_preserves_date_range_text():
    result = parse_bulletin_transfer_text(
        TRANSFER_20260927,
        year=2026,
    )

    schedule = result.monthly_schedule

    assert (
        schedule.status
        == WeeklyStatus.VALUE
    )

    last = schedule.items[-1]

    assert (
        last.display_date
        == "9/24(목)~26(토)"
    )
    assert last.content == "추석 연휴"
