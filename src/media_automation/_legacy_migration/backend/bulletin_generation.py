import json,subprocess,uuid
from pathlib import Path

def generate_bulletin(store,body):
 if body['service']!='sunday':raise ValueError('주보는 주일 작업에서 제작합니다.')
 current=store.get(body['date'],'sunday')
 if current['revision']!=body['revision']:raise ValueError('최신 입력을 확인하세요.')
 if current['data'].get('fields',{}).get('확정 주보 호수',{}).get('state')!='VALUE':raise ValueError('주보 호수를 확인하세요.')
 root=Path(__file__).parent
 with store.connect() as db:
  db.execute('CREATE TABLE IF NOT EXISTS bulletin_settings (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)')
  row=db.execute('SELECT payload FROM bulletin_settings WHERE id=1').fetchone()
 settings=json.loads(row[0]) if row else json.loads((root.parent/'bulletin-base-reference.json').read_text())
 directory=Path(store.path).with_suffix('.generated');directory.mkdir(exist_ok=True)
 ident=uuid.uuid4().hex;file=directory/(ident+'.pdf');payload=directory/(ident+'.input.json')
 payload.write_text(json.dumps({'date':body['date'],'data':current['data'],'settings':settings,'output':str(file.resolve())},ensure_ascii=False))
 try:
  process=subprocess.run(['/Users/moonaneul/Documents/media-automation/.venv/bin/python','-B',str(root/'bulletin_render.py'),str(payload)],capture_output=True,text=True,timeout=60)
  if process.returncode:raise ValueError('PDF 제작에 실패했습니다. 내용 분량과 입력을 확인하세요.')
  result=json.loads(process.stdout)
  (directory/(ident+'.json')).write_text(json.dumps(dict(result,format='pdf',fields=current['data']['fields']),ensure_ascii=False))
  return dict(result,file_id=ident,format='pdf',filename=body['date']+'-주보-검수전.pdf',visual_review_pending=True)
 except Exception:
  file.unlink(missing_ok=True);raise
 finally:payload.unlink(missing_ok=True)
