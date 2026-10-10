"""Ephemeral browser preview: upload once, convert, return PDF; keep no files.

Uses only a temporary directory that is removed after the request.
Original local file is read by the browser, never modified by this API.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import threading

from pypdf import PdfReader

from .pptx_preview import convert_pptx

MAX_PREVIEW_BYTES = 128 * 1024 * 1024
_CONVERT_LOCK = threading.Lock()


def preview_once(filename: str, content: bytes) -> bytes:
    if not isinstance(filename, str) or not filename or len(filename) > 200:
        raise ValueError("파일 이름을 확인해주세요.")
    if Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise ValueError("경로가 포함된 파일 이름은 사용할 수 없습니다.")
    extension = Path(filename).suffix.lower()
    if extension not in {".pptx", ".pdf"}:
        raise ValueError("PPTX와 PDF 파일만 미리볼 수 있습니다.")
    if not isinstance(content, bytes) or not 0 < len(content) <= MAX_PREVIEW_BYTES:
        raise ValueError("파일 크기는 1바이트 이상 128MiB 이하여야 합니다.")

    if extension == ".pdf":
        try:
            if not PdfReader(BytesIO(content)).pages:
                raise ValueError("페이지가 없는 PDF는 표시할 수 없습니다.")
        except Exception as exc:
            raise ValueError("유효한 PDF 파일이 아닙니다.") from exc
        return content

    if not _CONVERT_LOCK.acquire(blocking=False):
        raise ValueError("다른 PPTX 미리보기 변환이 진행 중입니다. 잠시 후 다시 시도해주세요.")
    try:
        with TemporaryDirectory(prefix="media-preview-once-") as directory:
            folder = Path(directory)
            source = folder / "uploaded.pptx"
            output = folder / "preview.pdf"
            source.write_bytes(content)
            convert_pptx(source, output)
            return output.read_bytes()
    finally:
        _CONVERT_LOCK.release()
