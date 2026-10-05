from pathlib import Path

import yaml

from media_automation.bulletin.build import (
    build_bulletin_from_files,
)


def test_build_bulletin_from_files(
    tmp_path: Path,
):
    sunday_path = (
        tmp_path / "sunday.yaml"
    )
    transfer_path = (
        tmp_path / "transfer.txt"
    )
    output_path = (
        tmp_path / "bulletin.pdf"
    )

    sunday = {
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
                "title": "봉헌",
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
                "reference": "히 11:1~3",
            },
            "additional_scripture": {
                "status": "UNSET",
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
                "status": "UNSET",
            },
            "afternoon_service": {
                "status": "UNSET",
            },
            "monthly_schedule": {
                "status": "UNSET",
            },
            "cell_group": {
                "status": "UNSET",
            },
        },
    }

    sunday_path.write_text(
        yaml.safe_dump(
            sunday,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    transfer_path.write_text(
        """
9/27

cf) 오후 예배 : 생명의 삶 3주차
찬양 : 337, 430장, 주님 말씀하시면

*설교 중 읽을 말씀 ☞

<교회 소식>
1. 교회 소식 A

<9월 사역 일정>
9/24(목)~26(토) : 추석 연휴

<목장 말씀 나누기>
<히 11:1~3 / 살아 있는 믿음>
1. 질문 A
2. 질문 B
3. 질문 C
4. 질문 D
""",
        encoding="utf-8",
    )

    result = build_bulletin_from_files(
        sunday_yaml=sunday_path,
        transfer_text=transfer_path,
        output_pdf=output_path,
    )

    assert output_path.exists()
    assert output_path.read_bytes().startswith(
        b"%PDF"
    )

    assert (
        result.merge.sunday
        .worship.additional_scripture.status.value
        == "NONE"
    )

    assert (
        result.merge.praise_raw.value
        == "337, 430장, 주님 말씀하시면"
    )


def test_transfer_source_can_be_hwp(
    tmp_path,
    monkeypatch,
):
    import media_automation.bulletin.build as build

    hwp = tmp_path / "transfer.hwp"
    hwp.write_bytes(b"dummy")

    expected = """
9/27
cf) 오후 예배 : 테스트
"""

    monkeypatch.setattr(
        build,
        "extract_hwp_text",
        lambda path: expected,
    )

    assert (
        build._load_transfer_source(hwp)
        == expected
    )
