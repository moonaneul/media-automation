"""Extract HWP5 notice text without user-specific absolute paths."""
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

MAX_NOTICE_BYTES = 8 * 1024 * 1024
WORKER = ("import sys; from media_automation.bulletin.hwp import extract_hwp_text; "
          "sys.stdout.write(extract_hwp_text(sys.argv[1]))")

def extract_notice(filename: str, content: bytes) -> str:
    if not isinstance(filename,str) or not filename or len(filename)>200 or Path(filename).name!=filename or '/' in filename or '\\' in filename or Path(filename).suffix.lower() not in {'.hwp','.hwpx'}:
        raise ValueError('HWP/HWPX 파일 이름을 확인해주세요.')
    if not isinstance(content,bytes) or not 0<len(content)<=MAX_NOTICE_BYTES:
        raise ValueError('안내문 파일은 1바이트 이상 8MiB 이하여야 합니다.')
    if Path(filename).suffix.lower()=='.hwpx':
        raise ValueError('HWPX 추출은 아직 지원되지 않습니다. HWP5 또는 TXT를 사용해주세요.')
    with TemporaryDirectory(prefix='media-hwp-notice-') as folder:
        p=Path(folder)/'notice.hwp'
        p.write_bytes(content)
        try:
            r=subprocess.run([sys.executable,'-B','-c',WORKER,str(p)],capture_output=True,text=True,timeout=20,check=False)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise ValueError('HWP 파일을 읽는 동안 오류가 발생했습니다.') from exc
        if r.returncode or not r.stdout.strip() or len(r.stdout.encode('utf-8'))>1024*1024:
            raise ValueError('HWP5 파일을 읽지 못했습니다. 문서 형식을 확인해주세요.')
        return r.stdout
