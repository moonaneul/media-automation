import json
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize('kind,status,expected_format', [
    ('ppt', 200, 'pptx'), ('pdf', 200, 'pdf'), ('ppt', 404, 'pptx')
])
def test_download_preflights_then_uses_browser_stream(kind, status, expected_format):
    html = Path('src/media_automation/web/original/ui/index.html').read_text()
    source = html[html.index('async function downloadOutput()'):html.index("$('download').onclick=downloadOutput;")]
    driver = r'''
    const output=process.argv[1],status=Number(process.argv[2]);
    const button={disabled:false};let requested='',message='',clicked=false,method='';
    const $=()=>button;
    const record=()=>({outputs:{[output]:{fileId:'abc',filename:'test'}}});
    const msg=text=>message=text;
    const node=()=>({click(){clicked=true;},remove(){},href:'',download:''});
    const document={body:{append(){}}};
    const fetch=async (url,options)=>{requested=url;method=options.method;
      return {ok:status===200,status,headers:{get:()=>String(60*1024*1024)}};};
    ''' + source + '''
    downloadOutput().then(()=>console.log(JSON.stringify({requested,method,message,clicked,disabled:button.disabled})));
    '''
    result = json.loads(subprocess.check_output(['node', '-e', driver, kind, str(status)], text=True))
    assert result['requested'].endswith('format=' + expected_format)
    assert result['method'] == 'HEAD'
    assert result['disabled'] is False
    if status == 200:
        assert result['clicked']
        assert '다운로드를 시작' in result['message']
    else:
        assert not result['clicked']
        assert '파일을 찾지 못했습니다' in result['message']


def test_download_does_not_allocate_browser_blob():
    source = Path('src/media_automation/web/original/ui/index.html').read_text()
    handler = source[source.index('async function downloadOutput()'):source.index("$('download').onclick=downloadOutput;")]
    assert "method:'HEAD'" in handler
    assert 'response.blob()' not in handler
    assert 'URL.createObjectURL' not in handler
