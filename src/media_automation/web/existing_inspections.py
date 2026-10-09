"""Read-only copies of pre-existing worship outputs in separate inspection sessions.

Never stages an imported file as a production-job input or artifact.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4

from . import qa_review

MAX_FILE = 128 * 1024 * 1024
SERVICES = {"wednesday", "sunday", "friday_zoom", "friday_in_person", "bulletin"}
_ID = re.compile(r"[0-9a-f]{32}\Z")
_NAME = re.compile(r"[\x00-\x1f\x7f]")


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _save(destination: Path, data: dict) -> None:
    temp = destination.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(destination)


class ExistingInspections:
    """Local-only inspection archive, independent of all ProductionJobs states."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def _dir(self, inspection_id: str) -> Path:
        if not _ID.fullmatch(inspection_id):
            raise ValueError("올바르지 않은 검수 ID입니다.")
        path = self.root / inspection_id
        if not path.is_dir() or path.is_symlink() or not (path / "inspection.json").is_file():
            raise ValueError("기존 파일 검수 작업을 찾을 수 없습니다.")
        return path

    def _meta(self, inspection_id: str) -> tuple[Path, dict, Path]:
        folder = self._dir(inspection_id)
        data = json.loads((folder / "inspection.json").read_text(encoding="utf-8"))
        suffix = data["suffix"]
        path = folder / ("source" + suffix)
        if path.is_symlink() or not path.is_file():
            raise ValueError("검수용 복사본이 없습니다.")
        return folder, data, path

    def create(self, service: str, day: str, filename: str, content: bytes) -> dict:
        if service not in SERVICES:
            raise ValueError("지원하지 않는 예배 종류입니다.")
        if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
            raise ValueError("날짜는 YYYY-MM-DD 형식으로 입력해주세요.")
        if not isinstance(filename, str) or not filename or len(filename) > 200:
            raise ValueError("원본 파일 이름을 확인해주세요.")
        if Path(filename).name != filename or "/" in filename or "\\" in filename or _NAME.search(filename):
            raise ValueError("파일 이름에 경로 또는 제어 문자가 들어 있습니다.")
        suffix = Path(filename).suffix.lower()
        if suffix != (".pdf" if service == "bulletin" else ".pptx"):
            raise ValueError("주보는 PDF, 예배 PPT는 PPTX 파일만 검수할 수 있습니다.")
        if not isinstance(content, bytes) or not 0 < len(content) <= MAX_FILE:
            raise ValueError("파일 크기는 1바이트 이상 128MiB 이하여야 합니다.")
        self.root.mkdir(parents=True, exist_ok=True)
        inspection_id = uuid4().hex
        folder = self.root / inspection_id
        folder.mkdir(mode=0o700)
        source = folder / ("source" + suffix)
        try:
            with source.open("xb") as handle:
                handle.write(content)
            data = {
                "inspection_id": inspection_id, "service": service, "date": day,
                "filename": filename, "suffix": suffix, "sha256": _digest(source),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "type": "existing_file_only",
            }
            _save(folder / "inspection.json", data)
            return self.get(inspection_id)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise

    def get(self, inspection_id: str) -> dict:
        folder, data, source = self._meta(inspection_id)
        result = dict(data)
        result["unchanged"] = _digest(source) == data["sha256"]
        # A copied file that was altered locally cannot be used as if verified.
        if result["unchanged"]:
            result["qa"] = qa_review.status(folder, source.name, source, data["service"])
        else:
            result["qa"] = {"available": False, "stale": True, "message": "검수용 파일 내용이 변경되었습니다."}
        result["preview"] = self.preview_status(inspection_id)
        return result

    def list(self) -> list[dict]:
        if not self.root.is_dir():
            return []
        result = []
        for folder in self.root.iterdir():
            if not folder.is_dir() or not _ID.fullmatch(folder.name):
                continue
            try:
                result.append(self.get(folder.name))
            except (ValueError, FileNotFoundError, OSError, KeyError, json.JSONDecodeError):
                continue
        return sorted(result, key=lambda item: item["created_at"], reverse=True)

    def _ready(self, inspection_id: str) -> tuple[Path, dict, Path]:
        folder, data, source = self._meta(inspection_id)
        if _digest(source) != data["sha256"]:
            raise ValueError("검수용 파일이 등록 이후 변경되었습니다. 새 검수 작업으로 등록해주세요.")
        return folder, data, source

    def inspect(self, inspection_id: str, reference: str | None = None) -> dict:
        folder, meta, source = self._ready(inspection_id)
        return qa_review.inspect(folder, source.name, source, meta["service"], reference)

    def confirm(self, inspection_id: str, payload: dict) -> dict:
        folder, meta, source = self._ready(inspection_id)
        return qa_review.confirm(folder, source.name, source, meta["service"], payload)

    def report(self, inspection_id: str) -> bytes:
        folder, meta, source = self._ready(inspection_id)
        return qa_review.report_bytes(folder, source.name, source, meta["service"])

    def preview_status(self, inspection_id: str) -> dict:
        folder, meta, source = self._meta(inspection_id)
        if _digest(source) != meta["sha256"]:
            return {"available": False, "message": "원본 사본이 변경되어 미리보기를 표시할 수 없습니다."}
        if meta["suffix"] == ".pdf":
            return {"available": True, "kind": "pdf", "message": "원본 PDF를 브라우저에서 표시합니다."}
        preview = folder / "preview" / "slides.pdf"
        details = folder / "preview" / "metadata.json"
        if preview.is_file() and details.is_file():
            data = json.loads(details.read_text(encoding="utf-8"))
            if data.get("sha256") == meta["sha256"]:
                return {"available": True, "kind": "converted_pdf",
                        "message": "PPTX를 변환한 PDF입니다. PowerPoint 실제 화면과 대조가 필요합니다."}
        return {"available": False, "kind": "pptx",
                "message": "PPTX 미리보기는 로컬 LibreOffice가 있을 때만 PDF 변환할 수 있습니다. PowerPoint 재생 검수는 별도입니다."}

    def build_preview(self, inspection_id: str) -> dict:
        folder, meta, source = self._ready(inspection_id)
        if meta["suffix"] == ".pdf":
            return self.preview_status(inspection_id)
        if self.preview_status(inspection_id)["available"]:
            return self.preview_status(inspection_id)
        converter = shutil.which("soffice") or shutil.which("libreoffice")
        if converter is None:
            raise ValueError("PPTX 미리보기를 위해 LibreOffice의 soffice 실행 파일이 필요합니다. 현재는 PDF만 바로 미리볼 수 있습니다.")
        # Conversion operates on a separate scratch copy, never on the imported source.
        with tempfile.TemporaryDirectory(prefix="media-preview-") as temporary:
            scratch = Path(temporary)
            copy = scratch / "presentation.pptx"
            shutil.copy2(source, copy)
            output = scratch / "render"
            output.mkdir()
            profile = (scratch / "office-profile").as_uri()
            try:
                subprocess.run(
                    [converter, f"-env:UserInstallation={profile}", "--headless",
                     "--convert-to", "pdf", "--outdir", str(output), str(copy)],
                    cwd=scratch, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    timeout=90, check=True,
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError("PPTX 변환에 실패했습니다. 원본 파일은 변경되지 않았습니다.") from exc
            candidate = output / "presentation.pdf"
            if not candidate.is_file() or candidate.stat().st_size == 0:
                raise ValueError("PPTX 미리보기 PDF가 생성되지 않았습니다.")
            destination = folder / "preview"
            destination.mkdir(exist_ok=True)
            with (destination / "slides.pdf").open("wb") as dest, candidate.open("rb") as src:
                shutil.copyfileobj(src, dest)
            _save(destination / "metadata.json", {"sha256": meta["sha256"],
                                                   "created_at": datetime.now(timezone.utc).isoformat(),
                                                   "method": "libreoffice"})
        return self.preview_status(inspection_id)

    def preview_bytes(self, inspection_id: str) -> bytes:
        folder, meta, source = self._ready(inspection_id)
        current = self.preview_status(inspection_id)
        if not current.get("available"):
            raise ValueError("아직 미리보기가 준비되지 않았습니다.")
        file = source if meta["suffix"] == ".pdf" else folder / "preview" / "slides.pdf"
        return file.read_bytes()
