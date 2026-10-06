from pathlib import Path

from media_automation.bulletin.document import (
    build_bulletin_document,
)
from media_automation.bulletin.reference import (
    parse_completed_bulletin_text,
)
from media_automation.weekly_data.models import (
    SundayData,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "bulletin_20260920_extracted.txt"
)


def _person(
    name: str,
    title: str | None = None,
):
    data = {
        "status": "VALUE",
        "person": name,
    }

    if title:
        data["title"] = title

    return data


def _norm(value: str | None) -> str:
    if value is None:
        return ""

    return "".join(value.split())


def make_sunday_20260920() -> SundayData:
    return SundayData.model_validate(
        {
            "service": "sunday",
            "date": "2026-09-20",
            "worship": {
                "leader": _person(
                    "\uc774\uc740\ucca0",
                    "\ubaa9\uc0ac",
                ),
                "praise_first": _person(
                    "\uc774\uad11\ubbfc",
                    "\ud615\uc81c",
                ),
                "praise_second": _person(
                    "\uc7a5\uae30\ud6c8",
                    "\ud615\uc81c",
                ),
                "preacher": _person(
                    "\uc774\uc740\ucca0",
                    "\ubaa9\uc0ac",
                ),
                "closing_prayer": _person(
                    "\uc774\uc740\ucca0",
                    "\ubaa9\uc0ac",
                ),
                "opening_songs": [
                    {"status": "NONE"},
                    {"status": "NONE"},
                    {"status": "NONE"},
                ],
                "separate_hymn": {
                    "status": "VALUE",
                    "title": "\ucc2c\uc1a1",
                    "hymn_number": 293,
                },
                "offering_hymn": {
                    "status": "VALUE",
                    "title": "\ubd09\ud5cc\ucc2c\uc1a1",
                    "hymn_number": 263,
                },
                "special_song": {
                    "status": "NONE",
                },
                "sermon_title": {
                    "status": "VALUE",
                    "text": "\uc774\uc6c3\uc758 \uacbd\uacc4\ub97c \ub118\uc5b4",
                },
                "scripture": {
                    "status": "VALUE",
                    "reference": "\ub9c8 5:43~48",
                },
                "additional_scripture": {
                    "status": "NONE",
                },
                "decision_hymn": {
                    "status": "VALUE",
                    "title": "\uacb0\ub2e8\ucc2c\uc1a1",
                    "hymn_number": 304,
                },
            },
            "serving": {
                "this_week": {
                    "first_service": {
                        "prayer": _person(
                            "\uc778\ub3c4\uc790"
                        ),
                        "offering_prayer": _person(
                            "\uc2e0\ubb34\uc21c",
                            "\uc790\ub9e4",
                        ),
                    },
                    "second_service": {
                        "prayer": _person(
                            "\uae40\ud55c\uc12d",
                            "\uc9d1\uc0ac",
                        ),
                        "offering_prayer": _person(
                            "\uc7a5\ub355\uc218",
                            "\ud615\uc81c",
                        ),
                    },
                    "dishwashing": _person(
                        "\uc704\uc724\uae30, \uae40\ubbfc\uc2dd"
                    ),
                    "wednesday_prayer": _person(
                        "\uc784\uc815\ud654"
                    ),
                },
                "next_week": {
                    "first_service": {
                        "prayer": _person(
                            "\uc778\ub3c4\uc790"
                        ),
                        "offering_prayer": _person(
                            "\uc774\uad11\ubbfc"
                        ),
                    },
                    "second_service": {
                        "prayer": _person(
                            "\uc704\uc724\uae30"
                        ),
                        "offering_prayer": _person(
                            "\ubb38\ud638\uc131"
                        ),
                    },
                    "dishwashing": _person(
                        "\uc774\ud558\uc120, \ubb38\ubc14\ub2e4"
                    ),
                    "wednesday_prayer": _person(
                        "\ud55c\uc1a1\ud76c"
                    ),
                },
            },
            "bulletin": {
                "number": {
                    "status": "VALUE",
                    "value": "13-38",
                },
                "church_news": {
                    "status": "VALUE",
                    "items": [
                        {
                            "text": "\uc624\ub298\ubd80\ud130 \uc0c8 \uac00\uc871\ubc18 \uacf5\ubd80\uac00 \uc2dc\uc791\ub429\ub2c8\ub2e4(12:45, \ubaa9\uc591\uc2e4)."
                        },
                        {
                            "text": "\uc624\ub298 \uc624\ud6c4 \uc2dc\uac04\uc740 \u2018\uc0dd\uba85\uc758 \uc0b6\u2019 2\uc8fc \ucc28\uc785\ub2c8\ub2e4."
                        },
                        {
                            "text": "\ucd94\uc11d \uc5f0\ud734(24~26\uc77c) \uae30\uac04\uc5d0 \ubaa8\ub4e0 \uad50\ud68c \uc0ac\uc5ed\uc740 \uc27d\ub2c8\ub2e4."
                        },
                    ],
                },
                "afternoon_service": {
                    "status": "VALUE",
                    "title": "\uc0dd\uba85\uc758 \uc0b6 2\uc8fc\ucc28",
                },
                "monthly_schedule": {
                    "status": "VALUE",
                    "items": [
                        {
                            "display_date": "9/6(\uc77c)",
                            "content": "\uc9d1\uc0ac \ubd80\ubd80 \ubaa8\uc784",
                        },
                        {
                            "display_date": "9/13(\uc77c)",
                            "content": "\uad50\ud68c \uccad\uc18c, \uc0dd\uba85\uc758 \uc0b6 \uac1c\uac15",
                        },
                        {
                            "display_date": "9/14(\uc6d4)",
                            "content": "\uc11c\uc6b8\uc9c0\uc5ed \ubaa9\ud68c\uc790 \uce5c\uad50\ud68c(\ud558\ub298\ube5b\uae30\uc068\uad50\ud68c)",
                        },
                        {
                            "display_date": "9/24(\ubaa9)~26(\ud1a0)",
                            "content": "\ucd94\uc11d \uc5f0\ud734",
                        },
                    ],
                },
                "cell_group": {
                    "status": "VALUE",
                    "scripture": "\ub9c8 5:43~48",
                    "title": "\uc774\uc6c3\uc758 \uacbd\uacc4\ub97c \ub118\uc5b4",
                    "questions": [
                        "\uc608\uc218\ub2d8\uaed8\uc11c \ub9d0\uc500\ud558\uc2e0 \u201c\uc774\uc6c3\u201d\uc758 \ubc94\uc8fc\ub294 \uc6b0\ub9ac\uac00 \uc0dd\uac01\ud558\ub294 \uc774\uc6c3\uacfc \uc5b4\ub5bb\uac8c \ub2e4\ub978\uac00\uc694?",
                        "\uad6c\uc57d(\ucd9c 23:4~5)\uc5d0\uc11c \uc6d0\uc218\uc758 \uc9d0\uc744 \ub3c4\uc640\uc8fc\ub77c\ub294 \uba85\ub839\uc740 \uc624\ub298\ub0a0 \uc5b4\ub5a4 \ubaa8\uc2b5\uc73c\ub85c \uc801\uc6a9\ub420 \uc218 \uc788\uc744\uae4c\uc694?",
                        "\uacf5\ub3d9\uccb4 \uc548\uc5d0\uc11c \uc774\uc6c3\uc0ac\ub791\uc744 \uc2e4\ucc9c\ud558\uae30 \uc704\ud574 \ud568\uaed8 \ud560 \uc218 \uc788\ub294 \uad6c\uccb4\uc801 \uc2e4\ucc9c\uc740 \ubb34\uc5c7\uc77c\uae4c\uc694?",
                        "\ud558\ub098\ub2d8\uaed8\uc11c \uc545\uc778\uacfc \uc120\uc778 \ubaa8\ub450\uc5d0\uac8c \ud587\ubcd5\uacfc \ube44\ub97c \uc8fc\uc2e0\ub2e4\ub294 \ub9d0\uc500\uc740 \uc6b0\ub9ac\uc5d0\uac8c \uc5b4\ub5a4 \ub3c4\uc804\uc744 \uc90d\ub2c8\uae4c?",
                    ],
                },
            },
        }
    )


def test_20260920_reference_matches_document_pipeline():
    reference = parse_completed_bulletin_text(
        FIXTURE.read_text(
            encoding="utf-8"
        )
    )

    document = build_bulletin_document(
        make_sunday_20260920()
    )

    # Cover
    assert (
        document.cover.bulletin_number
        == reference.bulletin_number
    )
    assert (
        document.cover.date_text
        == reference.date_text
    )

    # Worship order
    assert (
        document.worship.leader
        == reference.worship.leader
    )
    assert (
        document.worship.praise_first
        == reference.worship.praise_first
    )
    assert (
        document.worship.praise_second
        == reference.worship.praise_second
    )
    assert (
        document.worship.preacher
        == reference.worship.preacher
    )
    assert (
        document.worship.closing_prayer
        == reference.worship.closing_prayer
    )

    assert (
        document.worship.separate_hymn
        == reference.worship.hymn
    )
    assert (
        document.worship.offering_hymn
        == reference.worship.offering_hymn
    )
    assert (
        document.worship.scripture
        == reference.worship.scripture
    )
    assert (
        document.worship.sermon_title
        == reference.worship.sermon_title
    )
    assert (
        document.worship.decision_hymn
        == reference.worship.decision_hymn
    )

    # Worship-order personnel display
    assert (
        _norm(
            document.worship.first_service_prayer_display
        )
        == _norm(
            reference.worship.prayer_first
        )
    )
    assert (
        _norm(
            document.worship.second_service_prayer_display
        )
        == _norm(
            reference.worship.prayer_second
        )
    )
    assert (
        _norm(
            document.worship.first_service_offering_prayer_display
        )
        == _norm(
            reference.worship.offering_prayer_first
        )
    )
    assert (
        _norm(
            document.worship.second_service_offering_prayer_display
        )
        == _norm(
            reference.worship.offering_prayer_second
        )
    )

    # Serving table
    assert (
        document.worship.first_service_prayer
        == reference.this_week.first_prayer
    )
    assert (
        document.worship.first_service_offering_prayer
        == reference.this_week.first_offering_prayer
    )
    assert (
        document.worship.second_service_prayer
        == reference.this_week.second_prayer
    )
    assert (
        document.worship.second_service_offering_prayer
        == reference.this_week.second_offering_prayer
    )
    assert (
        document.worship.this_week_dishwashing
        == reference.this_week.dishwashing
    )
    assert (
        document.worship.this_week_wednesday_prayer
        == reference.this_week.wednesday_prayer
    )

    assert (
        document.worship.next_week_first_service_prayer
        == reference.next_week.first_prayer
    )
    assert (
        document.worship.next_week_first_service_offering_prayer
        == reference.next_week.first_offering_prayer
    )
    assert (
        document.worship.next_week_second_service_prayer
        == reference.next_week.second_prayer
    )
    assert (
        document.worship.next_week_second_service_offering_prayer
        == reference.next_week.second_offering_prayer
    )
    assert (
        document.worship.next_week_dishwashing
        == reference.next_week.dishwashing
    )
    assert (
        document.worship.next_week_wednesday_prayer
        == reference.next_week.wednesday_prayer
    )

    # Cell group
    assert (
        document.cell_group.scripture
        == reference.cell_group.scripture
    )
    assert (
        document.cell_group.title
        == reference.cell_group.title
    )
    assert (
        document.cell_group.questions
        == reference.cell_group.questions
    )

    # News
    assert (
        document.news.church_news
        == reference.church_news
    )

    # Monthly schedule
    schedule_lines = tuple(
        f"{date_text} : {content}"
        for date_text, content
        in document.news.monthly_schedule
    )

    assert (
        schedule_lines
        == reference.monthly_schedule
    )
