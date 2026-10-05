from pathlib import Path

from media_automation.bulletin.reference import (
    parse_completed_bulletin_text,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "bulletin_20260920_extracted.txt"
)


def test_parse_20260920_completed_bulletin():
    result = parse_completed_bulletin_text(
        FIXTURE.read_text(
            encoding="utf-8"
        )
    )

    # 표지
    assert result.bulletin_number == "13-38"
    assert (
        result.date_text
        == "2026년 9월 20일"
    )

    # 오전 예배
    assert (
        result.worship.leader
        == "이은철 목사"
    )

    assert (
        result.worship.praise_first
        == "이광민 형제"
    )
    assert (
        result.worship.praise_second
        == "장기훈 형제"
    )

    assert result.worship.hymn == "293장"

    assert (
        result.worship.prayer_first
        == "인 도 자"
    )
    assert (
        result.worship.prayer_second
        == "김한섭 집사"
    )

    assert (
        result.worship.offering_hymn
        == "263장"
    )

    assert (
        result.worship.offering_prayer_first
        == "신무순 자매"
    )
    assert (
        result.worship.offering_prayer_second
        == "장덕수 형제"
    )

    assert (
        result.worship.scripture
        == "마 5:43~48"
    )

    assert (
        result.worship.sermon_title
        == "이웃의 경계를 넘어"
    )

    assert (
        result.worship.decision_hymn
        == "304장"
    )

    assert (
        result.worship.closing_prayer
        == "이은철 목사"
    )

    # 이번 주 섬김
    assert (
        result.this_week.first_prayer
        == "인도자"
    )
    assert (
        result.this_week.first_offering_prayer
        == "신무순"
    )
    assert (
        result.this_week.second_prayer
        == "김한섭"
    )
    assert (
        result.this_week.second_offering_prayer
        == "장덕수"
    )
    assert (
        result.this_week.dishwashing
        == "위윤기, 김민식"
    )
    assert (
        result.this_week.wednesday_prayer
        == "임정화"
    )

    # 다음 주 섬김
    assert (
        result.next_week.first_offering_prayer
        == "이광민"
    )
    assert (
        result.next_week.second_prayer
        == "위윤기"
    )
    assert (
        result.next_week.second_offering_prayer
        == "문호성"
    )
    assert (
        result.next_week.dishwashing
        == "이하선, 문바다"
    )
    assert (
        result.next_week.wednesday_prayer
        == "한송희"
    )

    # 목장
    assert (
        result.cell_group.scripture
        == "마 5:43~48"
    )
    assert (
        result.cell_group.title
        == "이웃의 경계를 넘어"
    )
    assert len(
        result.cell_group.questions
    ) == 4

    # 소식 / 일정
    assert len(result.church_news) == 3
    assert len(
        result.monthly_schedule
    ) == 4

    assert (
        result.monthly_schedule[-1]
        == "9/24(목)~26(토) : 추석 연휴"
    )
