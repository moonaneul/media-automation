"""Register only the three missing bulletin originals; local connection is read-only."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

from cryptography.fernet import Fernet
from media_automation.cloud.artifacts import upload_verified
from media_automation.web.original.onedrive import OneDrive


class MemoryConnection:
    def __init__(self, data):
        self.data = data
    def read(self):
        return deepcopy(self.data)
    def write(self, data):
        self.data = deepcopy(data)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--database',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    folder=args.database.with_suffix('.onedrive')
    state=json.loads(Fernet((folder/'encryption.key').read_bytes()).decrypt((folder/'connection.enc').read_bytes()))
    cloud=OneDrive(SimpleNamespace(path=str(args.database)),connection_backend=MemoryConnection(state))
    source=cloud.selected('source')
    existing=[i for i in cloud.children(source['id']) if i.get('name')=='제작 공통 자료' and 'folder' in i]
    if len(existing)!=1:raise ValueError('Existing common runtime folder required')
    args.output.mkdir(parents=True,exist_ok=True)
    manifest=args.output/'bulletin-runtime.json'
    rows=json.loads(manifest.read_text()) if manifest.exists() else []
    known={r['path'] for r in rows}
    for name in ('original-design.pdf','original-regular.ttf','original-bold.ttf'):
        relative='assets/private/bulletin/'+name
        if relative in known:continue
        path=args.source_root/relative
        record=upload_verified(cloud,path,existing[0], 'bulletin-runtime-'+name,purpose='source')
        record['filename']=name
        rows.append({'path':relative,**record})
        manifest.write_text(json.dumps(rows,ensure_ascii=False,indent=2))
        print('새 주보 공통자료 검증:',name,flush=True)
    def sql(value):
        return "'"+str(value).replace("'","''")+"'"
    lines=['begin;']
    for r in rows:
        lines.append('insert into public.media_files(digest,filename,size,drive_id,item_id,item) values('+','.join([
            sql(r['digest']),sql(r['filename']),str(r['size']),sql(r['drive_id']),sql(r['item_id']),sql(json.dumps({k:v for k,v in r.items() if k!='path'},ensure_ascii=False))+'::jsonb'])+') on conflict(digest) do nothing;')
        lines.append('insert into public.media_runtime_assets(path,digest) values('+sql(r['path'])+','+sql(r['digest'])+') on conflict(path) do nothing;')
        lines.append('do $$ begin if not exists(select 1 from public.media_runtime_assets where path='+sql(r['path'])+' and digest='+sql(r['digest'])+') then raise exception \'Runtime mapping differs\'; end if; end $$;')
    lines.append('commit;')
    (args.output/'register_bulletin_runtime.sql').write_text('\n'.join(lines)+'\n')
    print('주보 공통자료 3개와 추가 등록 SQL 준비 완료. 기존 DB·원본·인증 파일은 변경하지 않았습니다.')


if __name__=='__main__':
    try:main()
    except Exception:raise SystemExit('주보 공통자료 준비를 완료하지 못했습니다. 비밀정보는 출력하지 않았습니다.')
