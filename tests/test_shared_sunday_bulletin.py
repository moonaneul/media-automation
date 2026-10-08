from datetime import date
from pathlib import Path

import pytest
import yaml

from media_automation.bulletin.source import find_transfer, register_transfer
from media_automation.bulletin.transfer import parse_bulletin_transfer_text
from media_automation.bulletin.weekly import (
    alignment_differences, merge_for_sunday, sermon_crosscheck,
)
from media_automation.weekly_data.models import SundayData
from test_bulletin_merge import make_sunday
from test_bulletin_cli import bulletin, configure_roots


def test_register_once_and_require_explicit_valid_replacement(tmp_path: Path):
    directory = tmp_path / "input" / "bulletin" / "20261004"
    first = tmp_path / "first.txt"
    first.write_text("10/4\n찬양 : 첫 자료\n", encoding="utf-8")
    registered = register_transfer(first, directory, date(2026, 10, 4))
    assert registered == directory / "transfer.txt"
    assert find_transfer(directory) == registered
    assert register_transfer(first, directory, date(2026, 10, 4)) == registered

    correction = tmp_path / "correction.txt"
    correction.write_text("10/4\n찬양 : 수정 자료\n", encoding="utf-8")
    with pytest.raises(ValueError, match="--replace"):
        register_transfer(correction, directory, date(2026, 10, 4))
    assert registered.read_bytes() == first.read_bytes()

    wrong_date = tmp_path / "wrong.txt"
    wrong_date.write_text("10/11\n", encoding="utf-8")
    with pytest.raises(ValueError, match="날짜가 다릅니다"):
        register_transfer(wrong_date, directory, date(2026, 10, 4), replace=True)
    assert registered.read_bytes() == first.read_bytes()

    assert register_transfer(correction, directory, date(2026, 10, 4), replace=True) == registered
    assert registered.read_bytes() == correction.read_bytes()


def test_notice_priority_and_shared_weekly_check():
    base = make_sunday()
    transfer = parse_bulletin_transfer_text(
        "9/27\n* 설교 중 읽을 말씀 ☞ 시 24:3~5\n", year=2026
    )
    intake = {"fields": {"additional_scripture": {"status": "provided"}}}
    merged = merge_for_sunday(base, transfer, intake)

    assert merged.worship.additional_scripture == base.worship.additional_scripture
    assert alignment_differences(merged, merged) == []
    stale = merged.model_copy(update={"worship": merged.worship.model_copy(update={
        "additional_scripture": base.worship.additional_scripture.model_copy(
            update={"reference": "시 99:1"}
        ),
    })})
    assert "worship.additional_scripture.reference" in alignment_differences(merged, stale)


def test_generic_news_notice_uses_transfer_details():
    base = make_sunday()
    transfer = parse_bulletin_transfer_text(
        "9/27\n<교회 소식>\n1. 이번 주 상세 광고\n<9월 사역 일정>\n",
        year=2026,
    )
    merged = merge_for_sunday(
        base, transfer,
        {"fields": {"church_news": {"status": "provided", "value": "있음"}}},
    )
    assert [item.text for item in merged.bulletin.church_news.items] == [
        "이번 주 상세 광고"
    ]


def test_bulletin_crosscheck_blocks_stale_sunday_weekly(tmp_path, monkeypatch):
    configure_roots(monkeypatch, tmp_path)
    base = make_sunday()
    date_value = "2026-09-27"
    intake = {"fields": {}}
    root = bulletin.SUNDAY_ROOT
    root.mkdir(parents=True)
    (root / "sunday-20260927-base.yaml").write_text(
        yaml.safe_dump(base.model_dump(mode="json"), allow_unicode=True),
        encoding="utf-8",
    )
    (root / "sunday_20260927_intake.yaml").write_text(
        yaml.safe_dump(intake), encoding="utf-8"
    )
    transfer = bulletin.week_dir(date_value) / "transfer.txt"
    transfer.parent.mkdir(parents=True)
    transfer.write_text("9/27\n", encoding="utf-8")

    current = base.model_dump(mode="json")
    bulletin.verify_shared_weekly(date_value, current, transfer)
    current["worship"]["sermon_title"]["text"] = "오래된 설교 제목"
    with pytest.raises(SystemExit, match="worship.sermon_title.text"):
        bulletin.verify_shared_weekly(date_value, current, transfer)


def test_pdf_builder_does_not_remerge_verified_weekly(tmp_path, monkeypatch):
    import media_automation.bulletin.build as build

    sunday = make_sunday()
    sunday = SundayData.model_validate({
        **sunday.model_dump(mode="json"),
        "bulletin": {**sunday.bulletin.model_dump(mode="json"),
                     "number": {"status": "VALUE", "value": "13-39"}},
    })
    sunday_file = tmp_path / "sunday.yaml"
    sunday_file.write_text(
        yaml.safe_dump(sunday.model_dump(mode="json"), allow_unicode=True),
        encoding="utf-8",
    )
    transfer = tmp_path / "transfer.txt"
    transfer.write_text("9/27\n*설교 중 읽을 말씀 ☞ 시 99:1\n", encoding="utf-8")
    captured = {}
    monkeypatch.setattr(build, "build_bulletin_document", lambda weekly: captured.setdefault("weekly", weekly))
    monkeypatch.setattr(build, "render_bulletin_pdf", lambda document, output: output)

    result = build.build_bulletin_from_files(
        sunday_yaml=sunday_file,
        transfer_source=transfer,
        output_pdf=tmp_path / "unused.pdf",
        already_merged=True,
    )
    assert result.merge.sunday.worship.additional_scripture == sunday.worship.additional_scripture
    assert captured["weekly"] == sunday


def test_crosscheck_flags_sermon_content_mismatch():
    transfer = parse_bulletin_transfer_text(
        "9/27\n<목장 말씀 나누기>\n<시 1:1 / 다른 제목>\n",
        year=2026,
    )
    assert sermon_crosscheck(make_sunday(), transfer) == [
        "설교 본문 ↔ 목장 본문",
        "설교 제목 ↔ 목장 제목",
    ]


@pytest.mark.parametrize("schedule", ["9/6(일) : 지난 일정", ""])
def test_stale_monthly_heading_rejects_replacement_without_erasing_input(tmp_path, schedule):
    directory = tmp_path / "registered"
    first = tmp_path / "first.txt"
    first.write_text("10/11\n<10월 사역 일정>\n", encoding="utf-8")
    registered = register_transfer(first, directory, date(2026, 10, 11))
    correction = tmp_path / "correction.txt"
    correction.write_text(f"10/11\n<9월 사역 일정>\n{schedule}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="월간 일정 제목의 월이 다릅니다"):
        register_transfer(correction, directory, date(2026, 10, 11), replace=True)
    assert registered.read_bytes() == first.read_bytes()


def test_current_month_schedule_allows_explicit_next_month_event():
    parsed = parse_bulletin_transfer_text(
        "10/11\n<10월 사역 일정>\n11/1(일) : 전달된 다음 달 행사\n", year=2026,
    )
    assert parsed.monthly_schedule.items[0].display_date == "11/1(일)"
