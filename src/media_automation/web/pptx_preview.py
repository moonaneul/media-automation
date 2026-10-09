"""PPTX preview renderer: Microsoft PowerPoint on Mac, LibreOffice otherwise.

Converts a temporary copy, validates PDF page count, never touches source.
This is visual preview only; audio, animation and permissions are not verified.
"""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from pptx import Presentation
from pypdf import PdfReader


_SCRIPT = '''
on run argv
    set pptFile to POSIX file (item 1 of argv)
    set pdfFile to POSIX file (item 2 of argv)
    tell application "Microsoft PowerPoint"
        activate
        open pptFile
        set openedDeck to active presentation
        try
            save openedDeck in pdfFile as save as PDF
        on error errorMessage
            close openedDeck saving no
            error errorMessage
        end try
        close openedDeck saving no
    end tell
end run
'''


def _powerpoint_available() -> bool:
    if sys.platform != "darwin" or not shutil.which("osascript"):
        return False
    candidates = (
        Path("/Applications/Microsoft PowerPoint.app"),
        Path.home() / "Applications/Microsoft PowerPoint.app",
    )
    return any(path.is_dir() for path in candidates)


def _libreoffice_binary() -> str | None:
    candidate = shutil.which("soffice") or shutil.which("libreoffice")
    if candidate:
        return candidate
    if sys.platform == "darwin":
        app = Path("/Applications/LibreOffice.app/Contents/MacOS/soffice")
        if app.is_file():
            return str(app)
    return None


def availability() -> tuple[str | None, str]:
    if _powerpoint_available():
        return "powerpoint", "맥 Microsoft PowerPoint를 이용해 PDF 미리보기를 만듭니다. 자동화 권한이 필요할 수 있습니다."
    if _libreoffice_binary():
        return "libreoffice", "LibreOffice로 PDF 미리보기를 만듭니다. PowerPoint와 차이가 있을 수 있습니다."
    return None, "PPTX 미리보기에 PowerPoint(macOS) 또는 LibreOffice가 필요합니다."


def convert_pptx(source: Path, destination: Path) -> str:
    """Write verified PDF only to destination; returns engine identifier."""
    engine, message = availability()
    if engine is None:
        raise ValueError(message)
    if source.suffix.lower() != ".pptx":
        raise ValueError("PPTX 미리보기에는 .pptx 파일만 사용할 수 있습니다.")
    slides = len(Presentation(str(source)).slides)
    if slides < 1:
        raise ValueError("슬라이드가 없는 PPTX는 미리보기를 생성할 수 없습니다.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("이미 미리보기가 있습니다. 기존 결과를 덮어쓰지 않습니다.")

    with tempfile.TemporaryDirectory(prefix="media-preview-") as folder:
        scratch = Path(folder)
        copied = scratch / "presentation.pptx"
        shutil.copy2(source, copied)
        out = scratch / "render"
        out.mkdir()
        generated = out / "presentation.pdf"
        try:
            if engine == "powerpoint":
                # PowerPoint for Mac sometimes requires the PDF file to exist first.
                generated.touch()
                subprocess.run(
                    ["osascript", "-e", _SCRIPT, str(copied), str(generated)],
                    cwd=scratch, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=120, check=True,
                )
            else:
                profile = (scratch / "office-profile").as_uri()
                subprocess.run(
                    [_libreoffice_binary(), f"-env:UserInstallation={profile}", "--headless",
                     "--convert-to", "pdf", "--outdir", str(out), str(copied)],
                    cwd=scratch, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    timeout=120, check=True,
                )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("PPTX 미리보기 변환 시간이 초과됐습니다. PowerPoint 상태를 확인해주세요.") from exc
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError("PPTX 변환에 실패했습니다. 맥 자동화 권한 및 PowerPoint 창을 확인해주세요.") from exc

        try:
            if not generated.is_file() or generated.stat().st_size < 100:
                raise ValueError("변환한 PDF 파일이 비어 있습니다.")
            pages = len(PdfReader(str(generated)).pages)
        except Exception as exc:
            raise ValueError("PPTX 변환 PDF가 올바르게 생성되지 않았습니다.") from exc
        if pages != slides:
            raise ValueError(f"미리보기 PDF 페이지 수({pages})와 원본 슬라이드 수({slides})가 다릅니다.")
        # Destination is a separate new file. No changes to source or temporary copy persist.
        with generated.open("rb") as src, destination.open("xb") as dst:
            shutil.copyfileobj(src, dst)
    return engine
