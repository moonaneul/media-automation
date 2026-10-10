"""Render the saved PPTX, without rebuilding or modifying it."""
import json
import subprocess
import threading
from pathlib import Path
from generation import RUNTIME,ROOT
LOCK=threading.Lock()

def preview(store,identifier,page):
    if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError('파일을 확인하세요.')
    if not isinstance(page,int) or page<1:raise ValueError('슬라이드 번호를 확인하세요.')
    directory=Path(store.path).with_suffix('.generated')
    ppt=directory/(identifier+'.pptx');report=directory/(identifier+'.json')
    if not ppt.is_file() or not report.is_file():raise FileNotFoundError()
    count=json.loads(report.read_text())['slide_count']
    if page>count:raise ValueError('슬라이드 번호를 확인하세요.')
    output=directory/f'{identifier}-slide-{page}.png'
    with LOCK:
        if not output.is_file():
            try:
                subprocess.run([str(RUNTIME/'node/bin/node'),str(ROOT/'friday-in-person-check/build/render-ppt.mjs'),str(ppt),str(output),str(page)],check=True,capture_output=True,timeout=60)
            except Exception:
                output.unlink(missing_ok=True)
                raise
    return output.read_bytes()
