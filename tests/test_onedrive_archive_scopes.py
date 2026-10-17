"""Archive browsing must use the configured worship folder, not only archive root.

Only GitHub-safe mocks. Actual OneDrive upload and playback require Mac checks.
"""
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest

from media_automation.web.original.onedrive_http import handle


@pytest.mark.parametrize('purpose', [
    'archive', 'archive_wednesday', 'archive_friday_zoom', 'archive_friday_in_person',
    'archive_sunday_ppt', 'archive_sunday_pdf',
])
def test_archive_viewer_scoped_folder_route(purpose):
    queried = []
    class Cloud:
        def list_selected(self, p, identifier, query):
            queried.append((p, identifier, query))
            return [{'id':'uploaded','name':'2026-10-16-friday.pptx','file':{}}]
    class Handler:
        command = 'GET'
        headers = {}
        replies = []
        def reply(self, status, body):
            self.replies.append((status, body))
    h=Handler()
    h.replies=[]
    path='/api/onedrive/files?purpose='+purpose
    assert handle(Cloud(), h, urlsplit(path), 'http://localhost:18877', True, 'test-session', True)
    assert queried==[(purpose,None,'')]
    assert h.replies[-1][0]==200
    assert h.replies[-1][1]['items'][0]['id']=='uploaded'


def test_archive_viewer_does_not_allow_unrelated_one_drive_purpose():
    class Cloud:
        def list_selected(self, purpose, identifier, query):
            raise AssertionError('Unauthorised purpose should be blocked')
    class Handler:
        command='GET'
        headers={}
        replies=[]
        def reply(self, status, body):
            self.replies.append((status,body))
    h=Handler()
    h.replies=[]
    assert handle(Cloud(),h,urlsplit('/api/onedrive/files?purpose=private'), 'http://localhost:18877',True,'s',True)
    assert h.replies[-1][0]==400


def test_archive_ui_uses_selected_folder_scopes():
    from pathlib import Path
    src=Path('src/media_automation/web/original/ui/onedrive.js').read_text()
    chunk=src[src.index('async function archives('):src.index('async function archiveCurrent(')]
    assert 'state?.folders?.[key]' in chunk
    assert "encodeURIComponent(chosen)" in chunk
    assert "archives(chosen,item.id)" in chunk
    assert "OneDrive에서 열기" in chunk
    # Only user-selected folders, not Graph global search.
    assert 'search(q=' not in chunk


def test_archive_retry_reports_failed_prerequisites():
    from pathlib import Path
    src=Path('src/media_automation/web/original/ui/onedrive.js').read_text()
    chunk=src[src.index('async function archiveCurrent('):src.index('async function syncOriginal(')]
    assert 'if(!(state.folders?.archive||state.folders?.[keyName]))requireBeforeUpload' in chunk
    assert 'status.textContent' in chunk
    assert 'finally{button.disabled=false;}' in chunk


def test_archive_browser_separates_prerequisite_from_real_transfer_errors(tmp_path):
    """Execute actual archiveCurrent JS: no upload before review; distinguish HTTP error."""
    import json
    import subprocess
    from pathlib import Path

    script = r"""
    const fs=require('fs');
    const src=fs.readFileSync(process.argv[1], 'utf8');
    const part=src.slice(src.indexOf(' async function archiveCurrent('),
                         src.indexOf(' async function syncOriginal('));
    const k='sunday:2026-10-18';
    const output={fileId:'f'.repeat(32),changed:false,complete:false};
    const app={output:'pdf',records:{[k]:{outputs:{pdf:output}}}};
    let count=0,failRemote=false;
    const status={textContent:''},button={disabled:false};
    const el=id=>id==='storage-status'?status:id==='cloud-archive-current'?button:null;
    const state={connected:true,folders:{archive:{id:'chosen'}}};
    const api=async(action,body)=>{
      if(action!=='archive')throw Error('unexpected request');
      count++;
      if(failRemote)throw Error('HTTP 403');
      return {item:{id:'remote-id',name:'test.pdf'},
              work:{data:app.records[k],revision:4}};
    };
    const refresh=async()=>{},key=()=>k,render=()=>{},persistDraft=()=>{},
          syncState=()=>({dirty:false,busy:false,revision:1}),msg=()=>{};
    const archiveCurrent=new Function('state','el','key','app','refresh',
      'api','syncState','render','persistDraft','msg',part+';return archiveCurrent;')(
      state,el,key,app,refresh,api,syncState,render,persistDraft,msg);
    (async()=>{
      let blocked=false;
      try{await archiveCurrent(k,'pdf');}
      catch(e){blocked=e.beforeUpload===true;}
      if(!blocked||count!==0||!status.textContent.startsWith('OneDrive 보관 준비 필요 ·')||button.disabled)
        throw Error('Pre-review should not be mislabeled as a failed upload');
      output.complete=true;
      await archiveCurrent(k,'pdf');
      if(count!==1||!status.textContent.startsWith('OneDrive 보관 완료 ·')||button.disabled)
        throw Error('Approved output did not trigger archive request');
      failRemote=true;
      let failed=false;
      try{await archiveCurrent(k,'pdf');}
      catch(e){failed=!e.beforeUpload;}
      if(!failed||count!==2||!status.textContent.startsWith('OneDrive 업로드 실패 ·')||button.disabled)
        throw Error('Actual request error not separated from review prerequisite');
      console.log(JSON.stringify({blocked,attempts:count,remoteError:failed}));
    })().catch(error=>{console.error(error);process.exit(1)});
    """
    path = Path('src/media_automation/web/original/ui/onedrive.js').resolve()
    outcome = subprocess.run(
        ['node', '-e', script, str(path)],
        capture_output=True, text=True, timeout=12, check=True,
    )
    assert json.loads(outcome.stdout) == {
        'blocked': True, 'attempts': 2, 'remoteError': True,
    }
