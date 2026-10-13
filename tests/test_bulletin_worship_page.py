from media_automation.bulletin.document import (
    BulletinWorshipPage,
)
from media_automation.bulletin.worship_page import (
    build_serving_rows,
    build_worship_order_rows,
)


def make_page():
    return BulletinWorshipPage(
        separate_hymn="337장",
        first_service_prayer="인도자",
        second_service_prayer="위윤기",
        offering_hymn="430장",
        first_service_offering_prayer=(
            "이광민"
        ),
        second_service_offering_prayer=(
            "문호성"
        ),
        scripture="히 11:1~3",
        sermon_title="살아 있는 믿음",
        decision_hymn="주님 말씀하시면",
        this_week_dishwashing=(
            "이하선, 문바다"
        ),
        this_week_wednesday_prayer=(
            "한송희"
        ),
        next_week_first_service_prayer="인도자",
        next_week_second_service_prayer="문희재",
        next_week_first_service_offering_prayer="김진아",
        next_week_second_service_offering_prayer="장기훈",
        next_week_dishwashing=(
            "한윤선, 이광민"
        ),
        next_week_wednesday_prayer=(
            "한미선"
        ),
        afternoon_service=(
            "생명의 삶 3주차"
        ),
    )


def test_build_worship_order_rows():
    rows = dict(
        build_worship_order_rows(
            make_page()
        )
    )

    assert rows["찬 송"] == "337장"

    assert rows["기 도"] == (
        "1부 인도자 / 2부 위윤기"
    )

    assert (
        rows["봉 헌 찬 송"]
        == "430장"
    )

    assert (
        rows["봉 헌 기 도"]
        == "1부 이광민 / 2부 문호성"
    )

    assert (
        rows["성 경 봉 독"]
        == "히 11:1~3"
    )

    assert (
        rows["말 씀 선 포"]
        == "살아 있는 믿음"
    )

    # 데이터에 없는 담당자는
    # 다른 담당자에서 추정하지 않는다.
    assert rows["경배와 찬양"] == ""
    assert rows["폐 회 기 도"] == ""


def test_build_serving_rows():
    rows = build_serving_rows(
        make_page()
    )

    assert rows[0] == (
        "이번 주 1부",
        "인도자",
        "이광민",
        "이하선, 문바다",
        "한송희",
    )

    assert rows[1] == (
        "이번 주 2부",
        "위윤기",
        "문호성",
        "",
        "",
    )

    assert rows[2] == (
        "다음 주 1부",
        "인도자",
        "김진아",
        "한윤선, 이광민",
        "한미선",
    )

    assert rows[3] == (
        "다음 주 2부",
        "문희재",
        "장기훈",
        "",
        "",
    )


def test_reference_columns_keep_content_and_service_roles_separate():
    from media_automation.bulletin.worship_page import build_worship_order_columns
    page = BulletinWorshipPage(separate_hymn='79장', scripture='단 1:8~9', sermon_title='믿음과 상황이 충돌할 때', preacher='이은철 목사', first_service_prayer='인도자', second_service_prayer='김한섭', closing_prayer='이은철 목사')
    rows = {''.join(label.split()): (content, person) for label, content, person in build_worship_order_columns(page)}
    assert rows['찬송'] == ('79장', '다 같이')
    assert rows['성경봉독'] == ('단 1:8~9', '인도자')
    assert rows['기도'] == ('', '1부 인도자\n2부 김한섭')
    assert rows['말씀선포'] == ('믿음과 상황이 충돌할 때', '이은철 목사')
    assert rows['폐회기도'] == ('', '이은철 목사')
