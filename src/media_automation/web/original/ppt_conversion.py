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
BUNDLED=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/soffice'

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
        # Some downloaded files have a legacy .ppt name but contain a valid PPTX package.
        # Keep original bytes intact and expose a correctly named cached copy.
        if valid(source):
            shutil.copyfile(source, target)
            return target
        binary=(str(Path('/Applications/LibreOffice.app/Contents/MacOS/soffice')) if Path('/Applications/LibreOffice.app/Contents/MacOS/soffice').is_file() else None) or shutil.which('soffice') or shutil.which('libreoffice') or (str(BUNDLED) if BUNDLED.is_file() else None)
        if not binary:raise RuntimeError('LibreOffice 미설치 · 구형 .ppt 자동 변환에는 LibreOffice가 필요합니다. Mac에는 /Applications/LibreOffice.app 설치 후 검수 서버를 다시 실행하세요.')
        with tempfile.TemporaryDirectory(dir=directory) as temp:
            temp=Path(temp);original=temp/'original.ppt';shutil.copyfile(source,original)
            command=[binary,'-env:UserInstallation='+(temp/'profile').as_uri(),
                     '--headless','--convert-to','pptx:Impress MS PowerPoint 2007 XML',
                     '--outdir',str(temp),str(original)]
            try:
                process=subprocess.run(command,capture_output=True,check=False,timeout=90)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError('LibreOffice 변환 시간 초과(90초) · 원본이 손상됐거나 변환 도구가 멈춘 상태입니다.') from exc
            if process.returncode:
                raise RuntimeError('LibreOffice가 .ppt 변환 작업을 실패했습니다. 파일을 PowerPoint 또는 LibreOffice에서 열고 PPTX로 다시 저장해 확인하세요.')
            result=temp/'original.pptx'
            if not valid(result):raise RuntimeError('LibreOffice 결과에 정상적인 PPTX가 없습니다. 원본 형식을 확인하거나 PPTX로 별도 저장해 주세요.')
            os.replace(result,target)
        return target

def conversion_status(source, filename):
    if Path(filename).suffix.lower()!='.ppt':return {'conversion_status':'not_needed'}
    try:
        convert_original(source)
        return {'conversion_status':'converted','converted_filename':Path(filename).stem+'.pptx'}
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as exc:
        explanation=str(exc) if isinstance(exc, RuntimeError) else '원본을 읽거나 변환하지 못했습니다. 원본 파일을 확인하세요.'
        return {'conversion_status':'failed','conversion_message':explanation+' 원본 파일은 그대로 보존됩니다.'}
