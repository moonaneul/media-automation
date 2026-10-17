"""Export library metadata and verified OneDrive references; no media payloads."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.web.original.onedrive import OneDrive, public_item

KEYS = {'media_songs': ('id',), 'media_files': ('digest',),
        'media_song_assets': ('song_id', 'digest'), 'media_asset_reviews': ('song_id', 'digest'),
        'media_attachments': ('day', 'service', 'slot'), 'media_bulletin_settings': ('id',),
        'media_archives': ('file_id',)}


def data_sql(tables):
    statements = ['begin;']
    for table, rows in tables.items():
        if table not in KEYS:
            raise ValueError('Unexpected table')
        data = json.dumps(rows, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
        tag = 'catalog_' + hashlib.sha256(data.encode()).hexdigest()
        if '$' + tag + '$' in data:
            raise ValueError('SQL delimiter conflict')
        value = '$' + tag + '$' + data + '$' + tag + '$::jsonb'
        keys = ','.join(KEYS[table])
        statements.append(f'''insert into public.{table}
select * from jsonb_populate_recordset(null::public.{table},{value})
on conflict do nothing;
do $check_{tag}$
begin
 if exists(
  select 1 from jsonb_populate_recordset(null::public.{table},{value}) wanted
  left join public.{table} actual using ({keys})
  where to_jsonb(wanted) is distinct from to_jsonb(actual)
 ) then raise exception 'Existing {table} differs. Import cancelled without overwriting.'; end if;
end;
$check_{tag}$;''')
    statements.extend(['commit;', "select '곡·원본·첨부·검수·주보 설정 복사 완료' as result;"])
    return '\n'.join(statements)


def export(database, additions, destination):
    if destination.exists():
        raise ValueError('Existing export will not be overwritten')
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.execute('begin')
        songs = [{'id': i, 'payload': json.loads(p)} for i, p in db.execute('select id,payload from songs order by id')]
        song_assets = [dict(zip(('song_id', 'digest', 'filename'), row)) for row in db.execute('select song_id,digest,filename from song_assets order by song_id,digest')]
        reviews = [{'song_id': s, 'digest': d, 'payload': json.loads(p)} for s, d, p in db.execute('select song_id,digest,payload from asset_reviews order by song_id,digest')]
        attachments = [dict(zip(('day', 'service', 'slot', 'filename', 'digest'), row)) for row in db.execute('select day,service,slot,filename,digest from attachments order by day,service,slot')]
        settings = [{'id': i, 'revision': r, 'payload': json.loads(p)} for i, r, p in db.execute('select id,revision,payload from bulletin_settings')]
        archives = [{'file_id': i, 'day': d, 'service': s, 'kind': k, 'item': public_item(json.loads(p))} for i, d, s, k, p in db.execute('select file_id,day,service,kind,item from cloud_archives order by file_id')]
        known = dict(db.execute('select digest,drive_item from cloud_song_sources'))
    added = json.loads(additions.read_text())['files']
    for row in added:
        if not row.get('verified_sha256'):
            raise ValueError('Unverified added original')
        known[row['sha256']] = row['item']['id']
    cloud = OneDrive(SimpleNamespace(path=str(database)))
    folder = cloud.selected('source')
    children = {item['id']: item for item in cloud.children(folder['id'])}
    names = {}
    for record in [*attachments, *song_assets]:
        names.setdefault(record['digest'], record['filename'])
    files = []
    for digest, filename in sorted(names.items()):
        if digest not in known:
            raise ValueError('An original is not mapped to OneDrive')
        item = children.get(known[digest])
        if item is None:
            item = cloud.item(known[digest])
            if not cloud.within(item, folder):
                raise ValueError('Mapped original outside selected source folder')
        path = database.with_suffix('.files') / digest
        if 'file' not in item or item.get('size') != path.stat().st_size:
            raise ValueError('Mapped original type/size differs')
        drive_id = item.get('parentReference', {}).get('driveId')
        if not drive_id:
            raise ValueError('Mapped original drive ID missing')
        files.append({'digest': digest, 'filename': filename, 'size': path.stat().st_size,
                      'drive_id': drive_id, 'item_id': item['id'], 'item': public_item(item)})
    tables = {'media_songs': songs, 'media_files': files, 'media_song_assets': song_assets,
              'media_asset_reviews': reviews, 'media_attachments': attachments,
              'media_bulletin_settings': settings, 'media_archives': archives}
    schema = (ROOT / 'deploy/cloud/004_library_metadata.sql').read_text()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('x') as stream:
        stream.write(schema + '\n' + data_sql(tables))
    report = {'counts': {t: len(r) for t, r in tables.items()}, 'sql': str(destination),
              'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}
    destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report['counts'], ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--additions', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    export(args.database, args.additions, args.output)


if __name__ == '__main__':
    main()
