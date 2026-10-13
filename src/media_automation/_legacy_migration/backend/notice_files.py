"""HWP notice extraction for the original blue app.

Keep the original /api/notice-file contract and 8MiB/20-second limits.
Use the repo HWP reader and active Python, never a hardcoded user path.
"""
from __future__ import annotations
import os
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[3]
MAX_BYTES = 8 * 1024 * 1024
_WORKER = (
    "import sys;sys.path.insert(0,sys.argv[1]);"
    "from media_automation.bulletin.hwp import extract_hwp_text;"
    "sys.stdout.write(extract_hwp_text(sys.argv[2]))"
)

def extract_notice(filename: str, content: bytes) -> str:
    if (
        not isinstance(filename, str)
        or not filename
        or len(filename) > 255
        or Path(filename).name != filename
        or '/' in filename
        or '\\' in filename
        or Path(filename).suffix.lower() not in ('.hwp', '.hwpx')
        or not isinstance(content, bytes)
        or not 0 < len(content) <= MAX_BYTES
    ):
        raise ValueError('안내문 HWP/HWPX 파일과 크기를 확인하세요.')
    suffix = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory(prefix='media-notice-') as directory:
        target = Path(directory) / ('notice' + suffix)
        target.write_bytes(content)
        try:
            result = subprocess.run(
                [sys.executable, '-B', '-c', _WORKER, str(SRC), str(target)],
                capture_output=True, text=True, timeout=20, check=False,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('HWP 파일 처리 중 오류가 발생했습니다.') from exc
        if result.returncode or not result.stdout.strip() or len(result.stdout.encode('utf-8')) > 1024 * 1024:
            raise ValueError('문서에서 텍스트를 추출하지 못했습니다.')
        return result.stdout
