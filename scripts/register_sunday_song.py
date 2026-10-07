from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from register_wednesday_song import date_token, load_yaml, run_script, stage_song


ROOT = Path(__file__).resolve().parents[1]
INTAKE_DIR = ROOT / "output" / "sunday_intake"
SONG_ROOT = ROOT / "input" / "sunday"

SLOT_ALIASES = {
    "1": "opening_song_1",
    "2": "opening_song_2",
    "3": "opening_song_3",
    "opening1": "opening_song_1",
    "opening2": "opening_song_2",
    "opening3": "opening_song_3",
    "opening_song_1": "opening_song_1",
    "opening_song_2": "opening_song_2",
    "opening_song_3": "opening_song_3",
    "separate": "separate_hymn",
    "separate_hymn": "separate_hymn",
    "offering": "offering_hymn",
    "offering_hymn": "offering_hymn",
    "special": "special_song",
    "special_song": "special_song",
    "decision": "decision_hymn",
    "decision_hymn": "decision_hymn",
}


def canonical_slot(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    try:
        return SLOT_ALIASES[normalized]
    except KeyError as exc:
        choices = "1, 2, 3, separate, offering, special, decision"
        raise ValueError(f"알 수 없는 슬롯입니다: {value!r} (사용 가능: {choices})") from exc


def register_song(
    date: str,
    slot: str,
    source: Path,
    *,
    replace: bool = False,
) -> tuple[Path, str, dict, bool]:
    token = date_token(date)
    field = canonical_slot(slot)
    intake_path = INTAKE_DIR / f"sunday_{token}_intake.yaml"
    checklist_path = INTAKE_DIR / f"sunday_{token}_song_checklist.yaml"
    manifest_path = INTAKE_DIR / f"sunday-{token}-songs.yaml"

    if not intake_path.is_file() or not checklist_path.is_file():
        raise FileNotFoundError(
            "이번 주 주일예배 안내와 악보 체크리스트가 준비되지 않았습니다.\n"
            "먼저 이번 주 안내로 python sunday.py start <안내파일> 을 실행하세요."
        )

    intake = load_yaml(intake_path)
    if intake.get("review_required"):
        raise ValueError(f"REVIEW 항목을 먼저 처리하세요: python sunday.py review {date}")

    record = intake.get("fields", {}).get(field, {})
    if record.get("status") not in {"provided", "asset_required"}:
        raise ValueError(f"이번 주 안내에 {field} 찬양이 없습니다.")

    checklist = load_yaml(checklist_path)
    item = next(
        (entry for entry in checklist.get("items", []) if entry.get("field") == field),
        None,
    )
    if item is None:
        raise ValueError(
            f"이번 주 체크리스트에 {field} 슬롯이 없습니다. "
            "안내에 없는 찬양을 임의로 등록하지 않습니다."
        )

    expected = item.get("expected_filename")
    if expected != f"{field}.pptx":
        raise ValueError(f"체크리스트의 {field} 파일명이 올바르지 않습니다: {expected!r}")

    destination = SONG_ROOT / token / expected
    action = stage_song(source, destination, replace=replace)

    # REVIEW에서 이번 주 곡명이 수정되었으면 안내의 최신 값을 표시한다.
    if item.get("title") != record.get("value"):
        item["title"] = record.get("value")
        checklist_path.write_text(
            yaml.safe_dump(checklist, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    run_script(
        "refresh_sunday_song_checklist.py",
        "--checklist", str(checklist_path),
        "--song-dir", str(destination.parent),
        allow=(0, 2),
    )

    refreshed = load_yaml(checklist_path)
    refreshed_item = next(
        entry for entry in refreshed.get("items", []) if entry.get("field") == field
    )
    if not refreshed_item.get("file"):
        raise RuntimeError("파일 등록 뒤 체크리스트가 READY로 갱신되지 않았습니다.")

    all_ready = all(entry.get("file") for entry in refreshed.get("items", []))
    manifest_ready = False
    if all_ready:
        resume_code = run_script(
            "resume_sunday_week.py", "--date", date, allow=(0, 2, 3)
        )
        manifest_ready = resume_code == 0 and manifest_path.is_file()

    return destination, action, refreshed_item, manifest_ready


def main() -> None:
    parser = argparse.ArgumentParser(
        description="사용자 제공 주일예배 악보 PPT를 이번 주 슬롯에 등록합니다."
    )
    parser.add_argument("date")
    parser.add_argument("slot", help="1, 2, 3, separate, offering, special, decision")
    parser.add_argument("file")
    parser.add_argument("--replace", action="store_true", help="기존 슬롯 파일 교체")
    args = parser.parse_args()

    try:
        destination, action, item, manifest_ready = register_song(
            args.date, args.slot, Path(args.file), replace=args.replace
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    action_label = {
        "copied": ".pptx 원본을 복사했습니다.",
        "converted": ".ppt 원본을 별도 .pptx 파일로 변환했습니다.",
        "already_registered": "이미 올바른 슬롯에 등록된 파일입니다.",
    }[action]
    print("\n=== SUNDAY SONG REGISTERED ===")
    print(f"slot     : {item['field']}")
    print(f"title    : {item.get('title') or ''}")
    print(f"file     : {destination}")
    print(f"result   : {action_label}")
    print(f"manifest : {'UPDATED' if manifest_ready else 'PENDING'}")
    print(f"NEXT: python sunday.py status {args.date}")


if __name__ == "__main__":
    main()
