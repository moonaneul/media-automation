"""Stream generated artifacts without loading the whole PPTX/PDF into Python RAM.

Authentication, job ownership and allowed-artifact checks MUST be performed by
Application.artifact before this function is called. Do not use for arbitrary paths.
"""
from __future__ import annotations

import mimetypes
import os
import stat
from pathlib import Path

CHUNK_SIZE = 1024 * 1024


def send_download(handler, target: Path) -> None:
    """Send an already-authorized local artifact as a binary HTTP response."""
    path = Path(target)
    # Open first so the headers describe the same inode we actually serve.
    with path.open('rb') as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise ValueError('일반 파일만 다운로드할 수 있습니다.')
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        handler.send_response(200)
        handler.send_header('Content-Type', mime)
        handler.send_header('Content-Length', str(info.st_size))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('Referrer-Policy', 'no-referrer')
        handler.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
        handler.end_headers()
        while True:
            chunk = source.read(CHUNK_SIZE)
            if not chunk:
                break
            handler.wfile.write(chunk)
