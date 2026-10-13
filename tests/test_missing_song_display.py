import json,re,subprocess
from pathlib import Path
import pytest

@pytest.mark.parametrize('kind,status,expected',[('song','input_pending','곡 입력 필요 · 자료 미연결'),('song','missing_song_asset','자료 미연결'),('song','original_inserted',''),('input','input_pending','입력 미제공')])
def test_preview_marks_every_uninserted_song(kind,status,expected):
    html=Path('src/media_automation/web/original/ui/index.html').read_text()
    function=html[html.index('function pptSectionWarning('):html.index('function renderResult()')]
    result=subprocess.check_output(['node','-e',function+'console.log(JSON.stringify(pptSectionWarning('+json.dumps({'kind':kind,'status':status,'key':'찬양 1'})+',{})));'],text=True)
    assert json.loads(result)==expected
    assert 'const warning=pptSectionWarning(item,report)' in html
