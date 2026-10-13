import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile
from production_order import build_order

BUILD_VERSION='2026-10-10-friday-template-1'

ROOT=Path(__file__).resolve().parent.parent
RUNTIME=Path('/Users/moonaneul/.cache/codex-runtimes/codex-primary-runtime/dependencies')

def generate(store,body):
    current=store.get(body['date'],body['service'])
    if current['revision']!=body['revision']:raise ValueError('입력이 변경됐습니다. 최신 입력으로 제작하세요.')
    data=current['data']
    order=build_order(body['groups'],data.get('fields',{}),body['service'])
    directory=Path(store.path).with_suffix('.generated')
    directory.mkdir(exist_ok=True)
    identifier=uuid.uuid4().hex
    file=directory/(identifier+'.pptx')
    report=directory/(identifier+'.json')
    payload=directory/(identifier+'.input.json')
    zoom=body['service']=='friday' and data.get('fridayMode','zoom')=='zoom'
    bible_process=subprocess.run(['/Users/moonaneul/Documents/media-automation/.venv/bin/python','-B',str(Path(__file__).with_name('bible_connection.py'))],input=json.dumps(order,ensure_ascii=False),text=True,capture_output=True,check=True,timeout=30,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
    bible=json.loads(bible_process.stdout)
    payload.write_text(json.dumps({'order':order,'bible':bible,'output':str(file.resolve()),'report':str(report.resolve()),'zoom':zoom,'service':body['service'],'date':body['date']},ensure_ascii=False))
    try:
        subprocess.run([str(RUNTIME/'python/bin/python3'),'-B',str(Path(__file__).with_name('friday_template.py')),str(payload.resolve())],check=True,capture_output=True,timeout=120)
        with zipfile.ZipFile(file) as z:
            if z.testzip() is not None:raise ValueError('PPT 파일 무결성 검사 실패')
        result=json.loads(report.read_text())
        from zoom_media import attach_videos,normalize_layout_ids,attach_background_music
        if zoom:
            result=attach_videos(file,result,{a['slot']:a for a in store.attachments(body['date'],body['service'])},Path(store.path).with_suffix('.files'))
            result=attach_background_music(file,result)
        if not zoom:
            sys.path.insert(0,str(ROOT/'friday-in-person-check'))
            from song_connection import resolve_song
            from attach_originals import attach_originals, engine
            from weekly_assets import resolve_attachment, prepend_start
            attachments={a['slot']:a for a in store.attachments(body['date'],body['service'])}
            connections={b['key']:(resolve_attachment(attachments[b['key']],Path(store.path).with_suffix('.files')) if b['key'] in attachments else resolve_song(b['content'],store.songs(),Path(store.path).with_suffix('.files'))) for b in order if b['kind']=='song'}
            if any(c['status']=='connected' for c in connections.values()):
                merged=directory/(identifier+'.merged.pptx')
                result=attach_originals(file,result,connections,merged)
                os.replace(merged,file)
            # The existing template builder already includes the service start slides.
            result['connections']=connections
        normalize_layout_ids(file)
        result['build_version']=BUILD_VERSION
        result['complete']=False
        result['visual_review_pending']=True
        report.write_text(json.dumps(result,ensure_ascii=False))
        return {'engine_version':BUILD_VERSION,'file_id':identifier,'filename':f"{body['date']}-{body['service']}-미완성.pptx",'slide_count':result['slide_count'],'unresolved':result['unresolved'],'complete':False,'visual_review_pending':True}
    except Exception:
        file.unlink(missing_ok=True);report.unlink(missing_ok=True)
        raise
    finally:payload.unlink(missing_ok=True)
