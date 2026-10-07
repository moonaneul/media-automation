from __future__ import annotations

import filecmp
import shutil
import tempfile
from datetime import date
from pathlib import Path

from media_automation.bulletin.hwp import extract_hwp_text
from media_automation.bulletin.transfer import parse_bulletin_transfer_text


SUPPORTED_SUFFIXES = {".hwp", ".hwpx", ".txt"}


def find_transfer(directory: Path) -> Path | None:
    candidates = sorted(
        path for path in directory.glob("transfer.*")
        if path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    if len(candidates) > 1:
        raise ValueError(
            "전달 주보 입력이 여러 개 있습니다:\n"
            + "\n".join(f"  - {path}" for path in candidates)
        )
    return candidates[0] if candidates else None


def read_transfer(path: Path) -> str:
    if path.suffix.lower() in {".hwp", ".hwpx"}:
        return extract_hwp_text(path)
    return path.read_text(encoding="utf-8-sig")


def validate_transfer_date(expected: date, path: Path) -> None:
    parsed = parse_bulletin_transfer_text(
        read_transfer(path), year=expected.year
    )
    if parsed.date != expected:
        raise ValueError(
            "입력한 날짜와 전달 주보 날짜가 다릅니다: "
            f"{expected} != {parsed.date}"
        )


def register_transfer(
    source: Path,
    directory: Path,
    expected: date,
    *,
    replace: bool = False,
) -> Path:
    source = source.resolve()
    if not source.is_file():
        raise ValueError(f"전달 주보 파일을 찾을 수 없습니다: {source}")
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("전달 주보는 .hwp / .hwpx / .txt 파일이어야 합니다.")

    # Validate before touching the registered copy. A rejected correction must
    # not erase the existing week's input.
    validate_transfer_date(expected, source)
    existing = find_transfer(directory)
    destination = directory / f"transfer{suffix}"
    if existing is not None:
        if existing.resolve() == source or filecmp.cmp(existing, source, shallow=False):
            return existing
        if not replace:
            raise ValueError(
                f"이미 등록된 전달 주보가 있습니다: {existing}\n"
                "수정본으로 바꾸려면 --replace를 사용하세요."
            )

    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=".transfer-", suffix=suffix, dir=directory, delete=False
    ) as temporary:
        staged = Path(temporary.name)
    try:
        shutil.copy2(source, staged)
        validate_transfer_date(expected, staged)
        staged.replace(destination)
        if existing is not None and existing != destination:
            existing.unlink()
    finally:
        staged.unlink(missing_ok=True)
    return destination
