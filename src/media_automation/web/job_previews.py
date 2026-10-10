"""Separate cached PDF previews for successfully generated job artifacts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path

from .pptx_preview import availability, convert_pptx

PREVIEW_TTL = timedelta(hours=24)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _directory(job_dir: Path, relative: str) -> Path:
    return job_dir / "previews" / hashlib.sha256(relative.encode("utf-8")).hexdigest()


def _expire_preview(target: Path) -> None:
    """Only derived PDF cache files are removable, never production outputs."""
    file = target / "slides.pdf"
    info = target / "metadata.json"
    if not file.exists() or not info.is_file() or (target / ".rendering.lock").exists():
        return
    try:
        meta = json.loads(info.read_text(encoding="utf-8"))
        stamp = datetime.fromisoformat(meta["created_at"])
        if stamp.tzinfo is None or datetime.now(timezone.utc) - stamp <= PREVIEW_TTL:
            return
    except (ValueError, KeyError, OSError, json.JSONDecodeError):
        return
    file.unlink(missing_ok=True)
    info.unlink(missing_ok=True)


def status(job_dir: Path, relative: str, artifact: Path) -> dict:
    suffix = artifact.suffix.lower()
    if suffix == ".pdf":
        return {"available": True, "method": "original",
                "message": "PDF를 브라우저에서 바로 표시합니다."}
    if suffix != ".pptx":
        raise ValueError("PDF와 PPTX만 미리볼 수 있습니다.")
    target = _directory(job_dir, relative)
    _expire_preview(target)
    output = target / "slides.pdf"
    metadata = target / "metadata.json"
    digest = _sha256(artifact)
    if output.is_file() and metadata.is_file():
        data = json.loads(metadata.read_text(encoding="utf-8"))
        if data.get("sha256") == digest:
            return {"available": True, "method": data.get("method"),
                    "message": "PPTX 변환 PDF입니다. 실제 애니메이션과 재생은 별도 확인이 필요합니다."}
    engine, message = availability()
    return {"available": False, "method": engine, "message": message}


def build(job_dir: Path, relative: str, artifact: Path) -> dict:
    current = status(job_dir, relative, artifact)
    if current["available"]:
        return current
    target = _directory(job_dir, relative)
    target.mkdir(parents=True, exist_ok=True)
    lock = target / ".rendering.lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(fd)
    except FileExistsError as exc:
        raise ValueError("같은 미리보기가 이미 생성 중입니다.") from exc
    try:
        if status(job_dir, relative, artifact)["available"]:
            return status(job_dir, relative, artifact)
        output = target / "slides.pdf"
        # Remove only derived stale previews; never overwrite the PPTX/PDF output.
        if output.exists():
            output.unlink()
        method = convert_pptx(artifact, output)
        metadata = {
            "sha256": _sha256(artifact), "method": method,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = target / "metadata.json.tmp"
        tmp.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        tmp.replace(target / "metadata.json")
    finally:
        lock.unlink(missing_ok=True)
    return status(job_dir, relative, artifact)


def read(job_dir: Path, relative: str, artifact: Path) -> bytes:
    current = status(job_dir, relative, artifact)
    if not current["available"]:
        raise ValueError("미리보기가 아직 생성되지 않았습니다.")
    path = artifact if artifact.suffix.lower() == ".pdf" else _directory(job_dir, relative) / "slides.pdf"
    return path.read_bytes()
