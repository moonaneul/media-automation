import json
import subprocess
from pathlib import Path
import pytest


@pytest.mark.parametrize('kind,status,expected_format',[
    ('ppt',200,'pptx'),('pdf',200,'pdf'),('ppt',404,'pptx')
])
def test_download_uses_selected_output_and_reports_missing_files(kind,status,expected_format):
    html=Path('src/media_automation/web/original/ui/index.html').read_text()
    source=html[html.index('async function downloadOutput()'):html.index("$('download').onclick=downloadOutput;")]
    driver=r'''
    const output=process.argv[1],status=Number(process.argv[2]);
    const button={disabled:false};let requested='',message='',clicked=false;
    const $=()=>button;const record=()=>({outputs:{[output]:{fileId:'abc',format:output==='ppt'?'pdf':'pptx',filename:'test'}}});
    const msg=text=>message=text;
    const node=()=>({click(){clicked=true;},remove(){}});
    const document={body:{append(){}}};
    const URL={createObjectURL(){return 'blob:test';},revokeObjectURL(){}};
    const setTimeout=()=>{};
    const fetch=async url=>{requested=url;return {ok:status===200,status,json:async()=>({error:'파일을 찾지 못했습니다.'}),blob:async()=>({size:10})};};
    '''+source+'''
    downloadOutput().then(()=>console.log(JSON.stringify({requested,message,clicked,disabled:button.disabled})));
    '''
    result=json.loads(subprocess.check_output(['node','-e',driver,kind,str(status)],text=True))
    assert result['requested'].endswith('format='+expected_format)
    assert result['disabled'] is False
    if status==200:
        assert result['clicked']
    else:
        assert not result['clicked']
        assert '파일을 찾지 못했습니다' in result['message']
