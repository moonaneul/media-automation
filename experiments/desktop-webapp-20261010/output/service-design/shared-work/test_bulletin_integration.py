import json,tempfile,threading,unittest,urllib.request,urllib.error,subprocess,io
from pathlib import Path
from server import make_server
from work_store import WorkStore
from pypdf import PdfReader
class BulletinIntegration(unittest.TestCase):
 def test_saved_input_download_and_revision(self):
  root=Path(__file__).resolve().parent
  code="const p=require(process.argv[1]),fs=require('fs');let r=p.parseBulletin(fs.readFileSync(process.argv[2],'utf8'));r.fields['확정 주보 호수']={state:'VALUE',value:'13-38'};console.log(JSON.stringify({fields:r.fields}));"
  data=json.loads(subprocess.check_output(['/Users/LOCAL_USER/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node','-e',code,str(root.parent/'blue-prototype/notice-parser.js'),str(root/'completed-bulletin-example.txt')]))
  with tempfile.TemporaryDirectory() as d:
   store=WorkStore(Path(d)/'test.db');saved=store.save('2026-09-20','sunday',0,data);server=make_server(store);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();url=f'http://127.0.0.1:{server.server_port}'
   body={'date':'2026-09-20','service':'sunday','revision':saved['revision'],'output':'pdf'}
   def build():return urllib.request.urlopen(urllib.request.Request(url+'/api/build',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}))
   try:
    result=json.load(build());download=urllib.request.urlopen(url+'/api/generated?id='+result['file_id']+'&format=pdf').read();pdf=PdfReader(io.BytesIO(download));self.assertEqual(len(pdf.pages),2);self.assertEqual(result['imposition'],[[4,1],[2,3]]);self.assertFalse(result['complete']);text=pdf.pages[1].extract_text()
    for k in ('성경 본문','설교 제목','별도 찬송','봉헌 찬송','결단 찬송','2부 기도 담당자','2부 봉헌기도 담당자'):self.assertIn(data['fields'][k]['value'],text)
    data['outputs']={'pdf':{'fileId':result['file_id'],'changed':False,'complete':False}}
    saved=store.save('2026-09-20','sunday',saved['revision'],data)
    completion={'date':'2026-09-20','service':'sunday','revision':saved['revision'],'file_id':result['file_id'],'reviewed':True}
    request=urllib.request.Request(url+'/api/complete-bulletin',data=json.dumps(completion).encode(),headers={'Content-Type':'application/json'})
    finished=json.load(urllib.request.urlopen(request))
    self.assertTrue(finished['data']['outputs']['pdf']['complete'])
    self.assertEqual(finished['data']['outputs']['pdf']['archiveStatus'],'pending_connection')
    data['fields']['설교 제목']['value']='수정된 제목'
    saved=store.save('2026-09-20','sunday',finished['revision'],data)
    completion['revision']=saved['revision']
    with self.assertRaises(urllib.error.HTTPError):
     urllib.request.urlopen(urllib.request.Request(url+'/api/complete-bulletin',data=json.dumps(completion).encode(),headers={'Content-Type':'application/json'}))
    with self.assertRaises(urllib.error.HTTPError):build()
   finally:server.shutdown();server.server_close();thread.join()
if __name__=='__main__':unittest.main()
