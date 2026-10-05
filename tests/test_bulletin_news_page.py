from media_automation.bulletin.news_page import (
    BulletinNewsStatic,
)


def test_regular_meetings_match_reference():
    static = BulletinNewsStatic()

    assert len(static.meetings) == 10

    assert static.meetings[0] == (
        "주일 오전 예배",
        "주일 오전 9시, 11시",
    )

    assert static.meetings[-1] == (
        "장년 제자 훈련반",
        "수요일 오후 8시 40분",
    )


def test_mission_and_core_values():
    static = BulletinNewsStatic()

    assert (
        "주님의 지상명령"
        in static.mission
    )

    assert len(
        static.core_values
    ) == 6

    assert (
        static.core_values[0]
        == "예배의 감동이 넘치는 교회"
    )

    assert (
        static.core_values[-1]
        == "가정을 말씀으로 세우는 교회"
    )

    assert (
        "상황과 무관하게"
        in static.joy_meaning
    )
