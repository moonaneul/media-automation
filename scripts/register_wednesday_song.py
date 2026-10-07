from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import yaml


ROOT = Path(__file__).resolve().parents[1]
INTAKE_DIR = ROOT / "output" / "wednesday_intake"
SONG_ROOT = ROOT / "input" / "wednesday"

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
    "additional": "additional_song",
    "additional_song": "additional_song",
    "decision": "decision_hymn",
    "decision_hymn": "decision_hymn",
}


def date_token(value: str) -> str:
    compact = value.replace("-", "").replace(".", "").strip()
    try:
        parsed = datetime.strptime(compact, "%Y%m%d")
    except ValueError as exc:
        raise ValueError("날짜는 YYYY-MM-DD, YYYY.MM.DD 또는 YYYYMMDD 형식이어야 합니다.") from exc
    return parsed.strftime("%Y%m%d")


def canonical_slot(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_")
    try:
        return SLOT_ALIASES[normalized]
    except KeyError as exc:
        choices = "1, 2, 3, additional, decision"
        raise ValueError(f"알 수 없는 슬롯입니다: {value!r} (사용 가능: {choices})") from exc


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def run_script(name: str, *args: str, allow: tuple[int, ...] = (0,)) -> int:
    command = [sys.executable, str(ROOT / "scripts" / name), *args]
    print("\n>>>", " ".join(command))
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode not in allow:
        raise RuntimeError(f"{name} failed with exit code {result.returncode}")
    return result.returncode


def convert_legacy_ppt(source: Path, destination: Path) -> None:
    if sys.platform != "win32":
        raise RuntimeError(".ppt 변환은 Windows와 Microsoft PowerPoint가 필요합니다.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(".ppt 변환에는 pywin32가 필요합니다.") from exc

    app = None
    presentation = None
    pythoncom.CoInitialize()
    try:
        app = win32com.client.DispatchEx("PowerPoint.Application")
        presentation = app.Presentations.Open(
            str(source),
            ReadOnly=True,
            Untitled=False,
            WithWindow=False,
        )
        # ppSaveAsOpenXMLPresentation = 24
        presentation.SaveAs(str(destination), 24)
    except Exception as exc:
        raise RuntimeError(f"PowerPoint에서 .ppt를 .pptx로 변환하지 못했습니다: {exc}") from exc
    finally:
        if presentation is not None:
            presentation.Close()
        if app is not None:
            app.Quit()
        pythoncom.CoUninitialize()


def stage_song(source: Path, destination: Path, *, replace: bool = False) -> str:
    source = source.expanduser().resolve()
    destination = destination.resolve()

    if not source.is_file():
        raise FileNotFoundError(f"악보 파일을 찾을 수 없습니다: {source}")
    if source.suffix.lower() not in {".ppt", ".pptx"}:
        raise ValueError("악보 파일은 .ppt 또는 .pptx 형식이어야 합니다.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    if source == destination:
        return "already_registered"
    if destination.exists() and not replace:
        raise FileExistsError(
            f"슬롯에 이미 파일이 있습니다: {destination}\n"
            "교체하려면 --replace를 추가하세요."
        )

    temporary = destination.with_name(
        f".{destination.stem}.{uuid4().hex}.tmp.pptx"
    )
    try:
        if source.suffix.lower() == ".ppt":
            convert_legacy_ppt(source, temporary)
            action = "converted"
        else:
            shutil.copy2(source, temporary)
            action = "copied"

        if not temporary.is_file() or temporary.stat().st_size == 0:
            raise RuntimeError("등록할 .pptx 파일이 생성되지 않았습니다.")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)

    return action


def register_song(
    date: str,
    slot: str,
    source: Path,
    *,
    replace: bool = False,
) -> tuple[Path, str, dict]:
    token = date_token(date)
    field = canonical_slot(slot)
    checklist = INTAKE_DIR / f"wednesday_{token}_song_checklist.yaml"
    weekly = INTAKE_DIR / f"wednesday-{token}.yaml"
    manifest = INTAKE_DIR / f"wednesday-{token}-songs.yaml"

    if not checklist.is_file() or not weekly.is_file():
        raise FileNotFoundError(
            "이번 주 수요예배 체크리스트가 준비되지 않았습니다.\n"
            f"먼저 실행: python wednesday.py resume {date}"
        )

    data = load_yaml(checklist)
    item = next(
        (candidate for candidate in data.get("items", []) if candidate.get("field") == field),
        None,
    )
    if item is None:
        raise ValueError(
            f"이번 주 체크리스트에 {field} 슬롯이 없습니다. "
            "안내에 없는 찬양을 임의로 등록하지 않습니다."
        )

    expected = item.get("expected_filename")
    if not expected:
        raise ValueError(f"체크리스트의 {field} 슬롯에 expected_filename이 없습니다.")

    destination = SONG_ROOT / token / expected
    action = stage_song(source, destination, replace=replace)

    run_script(
        "refresh_wednesday_song_checklist.py",
        "--checklist",
        str(checklist),
        "--song-dir",
        str(destination.parent),
        allow=(0, 2),
    )
    run_script(
        "build_wednesday_song_manifest.py",
        "--weekly",
        str(weekly),
        "--checklist",
        str(checklist),
        "--output",
        str(manifest),
    )

    refreshed = load_yaml(checklist)
    refreshed_item = next(
        candidate
        for candidate in refreshed.get("items", [])
        if candidate.get("field") == field
    )
    if not refreshed_item.get("file"):
        raise RuntimeError("파일 등록 뒤 체크리스트가 READY로 갱신되지 않았습니다.")

    return destination, action, refreshed_item


def main() -> None:
    parser = argparse.ArgumentParser(
        description="사용자 제공 수요예배 악보 PPT를 이번 주 슬롯에 등록합니다."
    )
    parser.add_argument("date")
    parser.add_argument("slot", help="1, 2, 3, additional, decision")
    parser.add_argument("file")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="이미 등록된 슬롯 파일을 명시적으로 교체",
    )
    args = parser.parse_args()

    try:
        destination, action, item = register_song(
            args.date,
            args.slot,
            Path(args.file),
            replace=args.replace,
        )
    except (FileNotFoundError, FileExistsError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    action_label = {
        "copied": ".pptx 원본을 복사했습니다.",
        "converted": ".ppt 원본을 별도 .pptx 파일로 변환했습니다.",
        "already_registered": "이미 올바른 슬롯에 등록된 파일입니다.",
    }[action]
    print("\n=== WEDNESDAY SONG REGISTERED ===")
    print(f"slot   : {item['field']}")
    print(f"title  : {item.get('title') or ''}")
    print(f"file   : {destination}")
    print(f"result : {action_label}")
    print(f"NEXT: python wednesday.py status {args.date}")


if __name__ == "__main__":
    main()
