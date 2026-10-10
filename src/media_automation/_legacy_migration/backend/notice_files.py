"""Read notice documents without changing the supplied file."""
import subprocess
import tempfile
from pathlib import Path

READER = Path('/Users/moonaneul/Documents/media-automation/src/media_automation/bulletin/hwp.py')
PYTHON = Path('/Users/moonaneul/Documents/media-automation/.venv/bin/python')

def extract_notice(filename, content):
    suffix=Path(filename).suffix.lower()
    if suffix not in ('.hwp','.hwpx') or not 0<len(content)<=8*1024*1024:
        raise ValueError('지원 파일과 크기를 확인하세요.')
    with tempfile.TemporaryDirectory(prefix='media-notice-') as directory:
        file=Path(directory)/('notice'+suffix)
        file.write_bytes(content)
        code='import importlib.util,sys; s=importlib.util.spec_from_file_location("hwp_reader",sys.argv[1]); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); print(m.extract_hwp_text(sys.argv[2]))'
        result=subprocess.run([str(PYTHON),'-B','-c',code,str(READER),str(file)],capture_output=True,text=True,timeout=20)
        if result.returncode or not result.stdout.strip() or len(result.stdout)>1024*1024:
            raise ValueError('파일을 읽지 못했습니다. 텍스트를 붙여 넣어 주세요.')
        return result.stdout
