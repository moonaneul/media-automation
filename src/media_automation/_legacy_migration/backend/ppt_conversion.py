"""Convert legacy originals locally; preserve bytes and cache by source hash."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import zipfile

_LOCK=threading.Lock()
BUNDLED=Path('/Users/moonaneul/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice')

def convert_original(source):
    source=Path(source)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    directory=source.parent/'converted';directory.mkdir(exist_ok=True)
    target=directory/(digest+'.pptx')
    def valid(file):
        try:
            with zipfile.ZipFile(file) as z:return 'ppt/presentation.xml' in z.namelist() and z.testzip() is None
        except (OSError,zipfile.BadZipFile):return False
    with _LOCK:
        if valid(target):return target
        binary=shutil.which('soffice') or shutil.which('libreoffice') or (str(BUNDLED) if BUNDLED.is_file() else None)
        if not binary:raise RuntimeError('무료 PPT 변환 도구를 사용할 수 없습니다.')
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            temp=Path(temp);original=temp/'original.ppt';shutil.copyfile(source,original)
            subprocess.run([binary,'-env:UserInstallation='+(temp/'profile').as_uri(),'--headless','--convert-to','pptx:Impress MS PowerPoint 2007 XML','--outdir',str(temp),str(original)],capture_output=True,check=True,timeout=90)
            result=temp/'original.pptx'
            if not valid(result):raise RuntimeError('PPTX 변환 결과를 확인하지 못했습니다.')
            os.replace(result,target)
        return target

def conversion_status(source, filename):
    if Path(filename).suffix.lower()!='.ppt':return {'conversion_status':'not_needed'}
    try:
        file=convert_original(source)
        return {'conversion_status':'converted','converted_filename':Path(filename).stem+'.pptx'}
    except Exception:return {'conversion_status':'failed','conversion_message':'자동 변환에 실패했습니다. 원본은 보존됐습니다. 다시 첨부하거나 제작을 다시 시도하세요.'}
