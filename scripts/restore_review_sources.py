#!/usr/bin/env python3
"""Restore *only* matching content-addressed originals to a disposable review store.

Never edits SQLite, source folders, original files, OneDrive, or other services.
Defaults to dry-run. --restore requires an explicit review root. Rejects symlinks
as source assets, target directory, or destination. Hashes must match the digest
recorded in the review database; filenames alone are never sufficient.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sqlite3
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path

DIGEST = re.compile(r"[0-9a-f]{64}\Z")
EXTENSIONS = {".ppt", ".pptx", ".mp4", ".mp3", ".wav", ".pdf"}
IGNORE_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache"}


def norm(text: str) -> str:
    return unicodedata.normalize("NFKC", text).casefold()


def digest_of(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def references(database: Path, matches: list[str]) -> dict[str, set[str]]:
    """Read only filename/digest references. Invalid digests are ignored."""
    found: dict[str, set[str]] = defaultdict(set)
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        for statement in (
            "SELECT filename,digest FROM attachments",
            "SELECT filename,digest FROM song_assets",
        ):
            try:
                rows = db.execute(statement)
            except sqlite3.OperationalError:
                continue
            for name, digest in rows:
                if not isinstance(name, str) or not isinstance(digest, str) or not DIGEST.fullmatch(digest):
                    continue
                if Path(name).suffix.lower() not in EXTENSIONS:
                    continue
                if matches and not any(norm(piece) in norm(name) for piece in matches):
                    continue
                found[digest].add(name)
    return found


def candidate_files(root: Path, targets: dict[str, set[str]]):
    """Bounded, read-only walk. Search stored hashes AND original filenames."""
    filenames: dict[str, set[str]] = defaultdict(set)
    for digest, names in targets.items():
        for name in names:
            filenames[norm(name)].add(digest)
    seen = set()
    for parent, directories, files in os.walk(root, topdown=True, followlinks=False):
        directories[:] = [
            name for name in directories
            if name not in IGNORE_DIRS and not (Path(parent) / name).is_symlink()
        ]
        for name in files:
            path = Path(parent) / name
            if path.is_symlink() or not path.is_file():
                continue
            exact_hash = name if DIGEST.fullmatch(name) else None
            hashes = ({exact_hash} if exact_hash in targets else set())
            hashes.update(filenames.get(norm(name), set()))
            # OneDrive archived originals sometimes have _<sha256> before suffix.
            suffix_hash = re.search(r"_([0-9a-f]{64})(?:\.[^.]+)?\Z", name)
            if suffix_hash and suffix_hash.group(1) in targets:
                hashes.add(suffix_hash.group(1))
            if not hashes:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path, hashes


def publish_verified(source: Path, destination: Path, expected: str) -> bool:
    """Publish without overwriting or linking to the original. Return False if already valid."""
    if destination.is_symlink():
        raise ValueError("검수용 파일이 심볼릭 링크입니다. 중단합니다: " + str(destination))
    if destination.exists():
        if digest_of(destination) == expected:
            return False
        raise ValueError("검수용 경로에 다른 내용의 파일이 있습니다. 덮어쓰지 않습니다.")
    target_dir = destination.parent
    if target_dir.is_symlink():
        raise ValueError("검수용 원본 폴더가 심볼릭 링크입니다. 중단합니다.")
    target_dir.mkdir(parents=True, exist_ok=True)
    if target_dir.is_symlink():
        raise ValueError("검수용 원본 폴더가 심볼릭 링크입니다. 중단합니다.")
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".recover-", suffix=".tmp", dir=target_dir, delete=False) as output:
            temporary = Path(output.name)
            with source.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    output.write(block)
        if digest_of(temporary) != expected:
            raise ValueError("복사 중 파일 해시가 달라져 게시하지 않았습니다.")
        # Exclusive hardlink INSIDE the review folder is atomic and cannot overwrite.
        try:
            os.link(temporary, destination)
        except FileExistsError:
            if destination.is_symlink() or digest_of(destination) != expected:
                raise ValueError("검수용 파일이 도중에 변경됐습니다. 덮어쓰지 않습니다.")
            return False
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def recover(database: Path, review_root: Path, sources: list[Path], *,
            matches: list[str] | None = None, restore: bool = False) -> dict[str, int]:
    if not database.is_file() or database.is_symlink():
        raise ValueError("검수용 DB를 찾을 수 없거나 심볼릭 링크입니다.")
    database = database.resolve()
    review_root = review_root.resolve()
    if not database.is_relative_to(review_root) or database == review_root:
        raise ValueError("검수 DB는 지정한 검수용 작업 폴더 안에 있어야 합니다.")
    files = database.with_suffix(".files")
    if files.is_symlink():
        raise ValueError("검수용 .files가 심볼릭 링크입니다. 원본 보호를 위해 중단합니다.")
    sources = [source.expanduser().resolve() for source in sources]
    if not sources:
        raise ValueError("찾을 원본 폴더를 --source로 지정하세요.")
    for source in sources:
        if not source.is_dir() or source.is_relative_to(review_root):
            raise ValueError("원본 검색 폴더는 검수용 폴더와 별도의 기존 디렉터리여야 합니다.")
    required = references(database, matches or [])
    pending = {}
    valid = 0
    for digest, names in required.items():
        dest = files / digest
        if dest.is_symlink():
            raise ValueError("검수용 원본 경로에 심볼릭 링크가 있습니다: " + digest)
        if dest.is_file() and digest_of(dest) == digest:
            valid += 1
        elif dest.exists():
            print("충돌 · 검수 폴더에 잘못된 파일 존재 (수정하지 않음):", ", ".join(sorted(names)))
        else:
            pending[digest] = names
    print(f"등록 원본 {len(required)}개 · 이미 정상 {valid}개 · 누락 {len(pending)}개")
    matched: dict[str, Path] = {}
    for source in sources:
        print("원본 검색:", source)
        for candidate, hashes in candidate_files(source, pending):
            actual = digest_of(candidate)
            if actual in hashes and actual not in matched:
                matched[actual] = candidate
                print("  해시 일치:", ", ".join(sorted(pending[actual])), "<-", candidate)
    copied = 0
    for digest, names in pending.items():
        candidate = matched.get(digest)
        if candidate is None:
            print("찾지 못함:", ", ".join(sorted(names)), "(등록된 해시와 일치하는 파일 없음)")
        elif restore:
            if publish_verified(candidate, files / digest, digest):
                copied += 1
                print("  검수용 폴더에 복사 완료:", ", ".join(sorted(names)))
        else:
            print("  복사 가능 · 실제 복사는 --restore 지정 후 실행:", ", ".join(sorted(names)))
    print(f"결과: 해시 일치 원본 {len(matched)}개, 새로 복사 {copied}개, 검색 실패 {len(pending)-len(matched)}개")
    print("원본 DB·원본 파일·OneDrive는 수정하지 않았습니다.")
    return {"registered": len(required), "already_valid": valid, "found": len(matched),
            "copied": copied, "missing": len(pending) - len(matched)}


def main(argv=None):
    parser = argparse.ArgumentParser(description="검수용 DB의 누락 악보/미디어 파일 복구 (해시 검증, 기본 읽기 전용)")
    parser.add_argument("database", type=Path)
    parser.add_argument("--review-root", type=Path, required=True, help="검수 프로젝트 최상위 폴더")
    parser.add_argument("--source", type=Path, action="append", required=True, help="기존 자료 검색 디렉터리")
    parser.add_argument("--match", action="append", default=[], help="대상 원본 파일명 일부 (복수 입력 가능)")
    parser.add_argument("--restore", action="store_true", help="해시 일치 파일만 검수용 .files에 복사")
    args = parser.parse_args(argv)
    recover(args.database, args.review_root, args.source,
            matches=args.match, restore=args.restore)


if __name__ == "__main__":
    main()
