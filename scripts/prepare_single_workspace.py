"""Safely stage *selected* old checkout inputs into a modern review checkout.

Read-only by default. --copy only adds missing files without overwriting.
Never moves/deletes originals, reuses credentials, switches Git refs, or syncs clouds.
Run while the original Windows app is stopped if requesting --copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

FOLDERS = ("sources", "input", "data/private", "assets/private")
OPTIONAL_OUTPUT = "output"
BLOCKED_NAMES = {".git", ".venv", "venv", "work.onedrive"}
BLOCKED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db-wal", ".db-shm", ".pem", ".key")
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for piece in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(piece)
    return result.hexdigest()


def is_blocked(path: Path) -> bool:
    return any(part.lower() in BLOCKED_NAMES for part in path.parts) or (
        path.name.lower().endswith(BLOCKED_SUFFIXES)
    ) or path.name.startswith(".env")


def _same_or_nested(a: Path, b: Path) -> bool:
    return a == b or a in b.parents or b in a.parents


def inspect(source: Path, destination: Path, *, include_output: bool = False) -> dict:
    """Return a private-name-free inventory and a file plan for the caller."""
    source, destination = source.expanduser().resolve(), destination.expanduser().resolve()
    if not (source.is_dir() and destination.is_dir()):
        raise ValueError("두 Git 작업 폴더가 모두 존재해야 합니다.")
    if _same_or_nested(source, destination):
        raise ValueError("원본과 대상이 같거나 서로 포함되는 폴더일 수 없습니다.")
    if not (source / ".git").exists() or not (destination / ".git").exists():
        raise ValueError("원본과 대상에 각각 .git 작업 폴더가 필요합니다.")

    entries = []
    folders = FOLDERS + ((OPTIONAL_OUTPUT,) if include_output else ())
    summary = dict(copy_candidates=0, identical=0, conflicts=0,
                   blocked=0, symlinks=0, lfs_placeholders=0, total_candidate_bytes=0)
    for folder in folders:
        base = source / folder
        if not base.exists():
            continue
        if base.is_symlink():
            summary["symlinks"] += 1
            continue
        for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
            parent = Path(dirpath)
            dirnames[:] = [d for d in dirnames if not (
                (parent / d).is_symlink() or is_blocked(Path(d))
            )]
            for name in filenames:
                old = parent / name
                rel = old.relative_to(source)
                new = destination / rel
                if old.is_symlink() or new.is_symlink() or any(
                    ancestor.is_symlink() for ancestor in new.parents
                    if ancestor != destination and destination in ancestor.parents
                ):
                    summary["symlinks"] += 1
                    continue
                if is_blocked(rel):
                    summary["blocked"] += 1
                    continue
                size = old.stat().st_size
                if size <= 200 and old.read_bytes().startswith(LFS_HEADER):
                    summary["lfs_placeholders"] += 1
                    continue
                if new.exists():
                    if new.is_file() and new.stat().st_size == size and digest(old) == digest(new):
                        status = "identical"
                    else:
                        status = "conflict"
                else:
                    status = "copy"
                summary[{"copy": "copy_candidates", "identical": "identical", "conflict": "conflicts"}[status]] += 1
                if status == "copy":
                    summary["total_candidate_bytes"] += size
                entries.append((old, new, status))
    return {"source": source, "destination": destination,
            "summary": summary, "entries": entries, "selected_folders": folders}


def _copy_no_replace(old: Path, new: Path) -> None:
    """Write a temp copy then atomically link into place; never overwrite target."""
    new.parent.mkdir(parents=True, exist_ok=True)
    if new.exists() or new.is_symlink():
        raise FileExistsError("새 폴더에 같은 이름의 파일이 이미 있습니다.")
    temp = new.with_name(new.name + ".import-" + uuid.uuid4().hex + ".tmp")
    try:
        shutil.copy2(old, temp, follow_symlinks=False)
        if digest(old) != digest(temp):
            raise IOError("복사한 파일의 SHA-256이 원본과 다릅니다.")
        os.link(temp, new)  # Fails if new already exists (Windows and Unix).
    finally:
        temp.unlink(missing_ok=True)


def run(source: Path, destination: Path, *, copy: bool = False,
        include_output: bool = False) -> dict:
    report = inspect(source, destination, include_output=include_output)
    summary = report["summary"]
    results = {
        "mode": "COPY_MISSING_ONLY" if copy else "DRY_RUN",
        "selected_folders": list(report["selected_folders"]),
        "copy_candidates": summary["copy_candidates"],
        "identical_files": summary["identical"],
        "conflicts": summary["conflicts"],
        "blocked_credentials_and_live_databases": summary["blocked"],
        "symlinks_skipped": summary["symlinks"],
        "lfs_placeholders_skipped": summary["lfs_placeholders"],
        "candidate_bytes": summary["total_candidate_bytes"],
        "copied": 0,
        "old_files_deleted": False,
        "existing_files_overwritten": False,
        "git_history_changed": False,
    }
    if copy:
        if summary["conflicts"] or summary["symlinks"] or summary["lfs_placeholders"]:
            raise ValueError(
                "충돌·링크·Git LFS 포인터가 있습니다. 자동 복사하지 않고 별도 확인합니다."
            )
        for old, new, status in report["entries"]:
            if status != "copy":
                continue
            _copy_no_replace(old, new)
            results["copied"] += 1
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--include-output", action="store_true",
                        help="기존 생성본도 포함, DB/토큰은 제외; 매우 큰 파일 가능")
    parser.add_argument("--copy", action="store_true",
                        help="명시할 때만 누락 파일을 원본 보존 상태로 복사")
    args = parser.parse_args()
    try:
        result = run(args.source, args.destination, copy=args.copy,
                     include_output=args.include_output)
    except (ValueError, IOError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
