import pytest

from media_automation.bulletin.merge import (
    merge_bulletin_transfer,
)
from media_automation.bulletin.transfer import (
    parse_bulletin_transfer_text,
)
from media_automation.weekly_data.models import (
    SundayData,
    WeeklyStatus,
)


def make_sunday() -> SundayData:
    return SundayData.model_validate(
        {
            "service": "sunday",
            "date": "2026-09-27",
            "worship": {
                "opening_songs": [
                    {
                        "status": "VALUE",
                        "title": "찬양1",
                    },
                    {
                        "status": "VALUE",
                        "title": "찬양2",
                    },
                    {
                        "status": "VALUE",
                        "title": "찬양3",
                    },
                ],
                "separate_hymn": {
                    "status": "VALUE",
                    "title": "찬송",
                },
                "offering_hymn": {
                    "status": "VALUE",
                    "title": "봉헌찬송",
                },
                "special_song": {
                    "status": "NONE",
                },
                "sermon_title": {
                    "status": "VALUE",
                    "text": "살아 있는 믿음",
                },
                "scripture": {
                    "status": "VALUE",
                    "reference": "히 11:1-3",
                },
                "additional_scripture": {
                    "status": "VALUE",
                    "reference": "시 1:1",
                },
                "decision_hymn": {
                    "status": "VALUE",
                    "title": "결단찬송",
                },
            },
            "serving": {
                "this_week": {
                    "first_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "기존1부기도",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "기존1부봉헌",
                        },
                    },
                    "second_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "기존2부기도",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "기존2부봉헌",
                        },
                    },
                    "dishwashing": {
                        "status": "VALUE",
                        "person": "기존설거지",
                    },
                    "wednesday_prayer": {
                        "status": "VALUE",
                        "person": "기존수요기도",
                    },
                },
                "next_week": {
                    "first_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "다음1부기도",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "다음1부봉헌",
                        },
                    },
                    "second_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "다음2부기도",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "다음2부봉헌",
                        },
                    },
                    "dishwashing": {
                        "status": "VALUE",
                        "person": "다음설거지",
                    },
                    "wednesday_prayer": {
                        "status": "VALUE",
                        "person": "다음수요기도",
                    },
                },
            },
            "bulletin": {
                "number": {
                    "status": "VALUE",
                    "value": "13-39",
                },
                "church_news": {
                    "status": "VALUE",
                    "items": [
                        {
                            "text": "기존 교회 소식",
                        },
                    ],
                },
                "afternoon_service": {
                    "status": "VALUE",
                    "title": "기존 오후예배",
                    "description": "기존 설명",
                },
                "monthly_schedule": {
                    "status": "VALUE",
                    "items": [
                        {
                            "date": "2026-09-01",
                            "content": "기존 일정",
                        },
                    ],
                },
                "cell_group": {
                    "status": "VALUE",
                    "scripture": "히 11:1-3",
                    "title": "기존 제목",
                    "questions": [
                        "기존1",
                        "기존2",
                        "기존3",
                        "기존4",
                    ],
                },
            },
        }
    )


TRANSFER = """
9/27

cf) 오후 예배 : 생명의 삶 3주차
찬양 : 337, 430장, 주님 말씀하시면

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

*설교 중 읽을 말씀 ☞

<교회 소식>
1. 교회 소식 A
2. 교회 소식 B

<9월 사역 일정>
9/6(일) : 집사 부부 모임
9/24(목)~26(토) : 추석 연휴

<목장 말씀 나누기>
<히 11:1~3 / 살아 있는 믿음>
1. 질문 A
2. 질문 B
3. 질문 C
4. 질문 D
"""


def test_merge_transfer_overrides_same_week_data():
    sunday = make_sunday()

    transfer = parse_bulletin_transfer_text(
        TRANSFER,
        year=2026,
    )

    result = merge_bulletin_transfer(
        sunday,
        transfer,
    )

    merged = result.sunday

    assert (
        merged.worship.additional_scripture.status
        == WeeklyStatus.NONE
    )

    assert (
        merged.bulletin.afternoon_service.title
        == "생명의 삶 3주차"
    )

    # 전달자료에서 수정하지 않은 description은 유지
    assert (
        merged.bulletin.afternoon_service.description
        == "기존 설명"
    )

    assert (
        merged.serving.this_week.second_service.prayer.person
        == "위윤기"
    )
    assert (
        merged.serving.this_week.wednesday_prayer.person
        == "한송희"
    )

    assert (
        len(
            merged.bulletin.church_news.items
        )
        == 2
    )

    schedule = (
        merged.bulletin.monthly_schedule.items
    )

    assert (
        schedule[1].display_date
        == "9/24(목)~26(토)"
    )
    assert (
        schedule[1].content
        == "추석 연휴"
    )

    assert (
        merged.bulletin.cell_group.title
        == "살아 있는 믿음"
    )
    assert (
        merged.bulletin.cell_group.questions
        == [
            "질문 A",
            "질문 B",
            "질문 C",
            "질문 D",
        ]
    )

    # 찬양 원문은 임의 매핑하지 않고 보존
    assert (
        result.praise_raw.value
        == "337, 430장, 주님 말씀하시면"
    )


def test_unset_transfer_keeps_sunday_data():
    sunday = make_sunday()

    transfer = parse_bulletin_transfer_text(
        "9/27",
        year=2026,
    )

    result = merge_bulletin_transfer(
        sunday,
        transfer,
    )

    merged = result.sunday

    assert (
        merged.worship.additional_scripture
        == sunday.worship.additional_scripture
    )
    assert (
        merged.serving
        == sunday.serving
    )
    assert (
        merged.bulletin
        == sunday.bulletin
    )


def test_merge_rejects_different_dates():
    sunday = make_sunday()

    transfer = parse_bulletin_transfer_text(
        "9/28",
        year=2026,
    )

    with pytest.raises(
        ValueError,
        match="날짜가 다릅니다",
    ):
        merge_bulletin_transfer(
            sunday,
            transfer,
        )
