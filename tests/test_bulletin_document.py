from media_automation.bulletin.document import (
    build_bulletin_document,
)
from media_automation.weekly_data.models import (
    SundayData,
)


def make_sunday():
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
                    "hymn_number": 337,
                },
                "offering_hymn": {
                    "status": "VALUE",
                    "title": "봉헌찬송",
                    "hymn_number": 430,
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
                    "status": "NONE",
                },
                "decision_hymn": {
                    "status": "VALUE",
                    "title": "주님 말씀하시면",
                },
            },
            "serving": {
                "this_week": {
                    "first_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "인도자",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "이광민",
                        },
                    },
                    "second_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "위윤기",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "문호성",
                        },
                    },
                    "dishwashing": {
                        "status": "VALUE",
                        "person": "이하선, 문바다",
                    },
                    "wednesday_prayer": {
                        "status": "VALUE",
                        "person": "한송희",
                    },
                },
                "next_week": {
                    "first_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "인도자",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "김진아",
                        },
                    },
                    "second_service": {
                        "prayer": {
                            "status": "VALUE",
                            "person": "문희재",
                        },
                        "offering_prayer": {
                            "status": "VALUE",
                            "person": "장기훈",
                        },
                    },
                    "dishwashing": {
                        "status": "VALUE",
                        "person": "한윤선, 이광민",
                    },
                    "wednesday_prayer": {
                        "status": "VALUE",
                        "person": "한미선",
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
                            "text": "교회 소식 A",
                        },
                        {
                            "text": "교회 소식 B",
                        },
                    ],
                },
                "afternoon_service": {
                    "status": "VALUE",
                    "title": "생명의 삶 3주차",
                },
                "monthly_schedule": {
                    "status": "VALUE",
                    "items": [
                        {
                            "display_date": "9/24(목)~26(토)",
                            "content": "추석 연휴",
                        },
                    ],
                },
                "cell_group": {
                    "status": "VALUE",
                    "scripture": "히 11:1~3",
                    "title": "살아 있는 믿음",
                    "questions": [
                        "질문1",
                        "질문2",
                        "질문3",
                        "질문4",
                    ],
                },
            },
        }
    )


def test_build_bulletin_document():
    document = build_bulletin_document(
        make_sunday()
    )

    assert (
        document.cover.bulletin_number
        == "13-39"
    )
    assert (
        document.cover.date_text
        == "2026년 9월 27일"
    )

    assert (
        document.worship.separate_hymn
        == "337장"
    )
    assert (
        document.worship.offering_hymn
        == "430장"
    )
    assert (
        document.worship.decision_hymn
        == "주님 말씀하시면"
    )

    assert (
        document.worship.second_service_prayer
        == "위윤기"
    )
    assert (
        document.worship.second_service_offering_prayer
        == "문호성"
    )

    assert (
        document.worship.this_week_dishwashing
        == "이하선, 문바다"
    )
    assert (
        document.worship.this_week_wednesday_prayer
        == "한송희"
    )

    assert (
        document.cell_group.scripture
        == "히 11:1~3"
    )
    assert len(
        document.cell_group.questions
    ) == 4

    assert (
        document.news.church_news
        == (
            "교회 소식 A",
            "교회 소식 B",
        )
    )

    assert (
        document.news.monthly_schedule[0]
        == (
            "9/24(목)~26(토)",
            "추석 연휴",
        )
    )
