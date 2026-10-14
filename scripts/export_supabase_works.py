"""Export a consistent read-only SQLite snapshot as conflict-safe Supabase SQL."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import UUID


def export(source: Path, destination: Path, administrator: str):
    administrator = str(UUID(administrator))
    if not source.is_file():
        raise ValueError('실사용 DB를 찾지 못했습니다.')
    if destination.exists() or destination.with_suffix('.sqlite3').exists():
        raise ValueError('이미 만든 이관 파일을 덮어쓰지 않습니다.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    snapshot = destination.with_suffix('.sqlite3')
    uri = source.resolve().as_uri() + '?mode=ro'
    with sqlite3.connect(uri, uri=True) as original, sqlite3.connect(snapshot) as backup:
        original.backup(backup)
    with sqlite3.connect(snapshot) as backup:
        if backup.execute('pragma quick_check').fetchone()[0] != 'ok':
            raise ValueError('DB 무결성 확인 실패')
        rows = backup.execute('select date,service,revision,payload,updated_at from works order by date,service').fetchall()
    records = []
    for day, service, revision, payload, updated in rows:
        if datetime.strptime(day, '%Y-%m-%d').strftime('%Y-%m-%d') != day:
            raise ValueError('날짜 형식 확인 필요')
        if service not in ('wednesday', 'friday', 'sunday') or type(revision) is not int or revision < 1:
            raise ValueError('예배 종류 또는 수정 버전 확인 필요')
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError('입력 JSON 객체 확인 필요')
        datetime.fromisoformat(updated)
        records.append({'day': day, 'service': service, 'revision': revision,
                        'payload': data, 'updated_at': updated})
    encoded = json.dumps(records, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    tag = 'media_data_' + digest
    block = 'media_import_' + digest
    if '$' + tag + '$' in encoded or '$' + block + '$' in encoded:
        raise ValueError('SQL 구분자 충돌')
    sql = '''-- Apply only to the dedicated church-media project after work storage setup.
-- Current work records are copied. Files and legacy integration history stay in the snapshot.
begin;
do $BLOCK$
declare
  v_rows jsonb := $TAG$DATA$TAG$::jsonb;
  v_item jsonb;
  v_day date;
  v_service text;
  v_revision bigint;
  v_payload jsonb;
  v_updated timestamptz;
  v_existing public.media_works%rowtype;
  v_history public.media_work_revisions%rowtype;
  v_admin uuid := 'ADMIN';
begin
  if not exists(select 1 from public.media_members where user_id=v_admin and role='admin' and active) then
    raise exception 'The expected church-media administrator was not found';
  end if;
  for v_item in select value from jsonb_array_elements(v_rows) loop
    v_day := (v_item->>'day')::date;
    v_service := v_item->>'service';
    v_revision := (v_item->>'revision')::bigint;
    v_payload := v_item->'payload';
    v_updated := (v_item->>'updated_at')::timestamptz;
    perform pg_advisory_xact_lock(hashtextextended(v_day::text || ':' || v_service, 0));
    select * into v_existing from public.media_works where day=v_day and service=v_service for update;
    if found and (v_existing.revision<>v_revision or v_existing.payload<>v_payload or v_existing.updated_at<>v_updated) then
      raise exception 'Cloud work differs: % / %. Import cancelled without overwriting.',v_day,v_service;
    end if;
    select * into v_history from public.media_work_revisions where day=v_day and service=v_service and revision=v_revision;
    if found and (v_history.payload<>v_payload or v_history.updated_at<>v_updated) then
      raise exception 'Cloud revision differs: % / %. Import cancelled.',v_day,v_service;
    end if;
    insert into public.media_works (day,service,revision,payload,updated_at,updated_by)
      values (v_day,v_service,v_revision,v_payload,v_updated,v_admin) on conflict do nothing;
    insert into public.media_work_revisions (day,service,revision,payload,updated_at,updated_by)
      values (v_day,v_service,v_revision,v_payload,v_updated,v_admin) on conflict do nothing;
  end loop;
end;
$BLOCK$;
commit;
select '예배 입력 COUNT개 복사 완료' as result;
'''
    sql = sql.replace('BLOCK', block).replace('TAG', tag).replace('ADMIN', administrator)
    sql = sql.replace('COUNT', str(len(records))).replace('DATA', encoded)
    # The payload is substituted last so user text cannot be interpreted as a template marker.
    with destination.open('x') as file:
        file.write(sql)
    report = {'count': len(records), 'payload_sha256': digest, 'snapshot': str(snapshot),
              'source': str(source), 'sql': str(destination),
              'scope': 'current works only; local files and legacy history retained in snapshot'}
    destination.with_suffix('.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--administrator', required=True)
    args = parser.parse_args()
    report = export(args.database, args.output, args.administrator)
    print('복사할 예배 입력:', report['count'])
    print('Supabase에 실행할 파일:', report['sql'])
    print('로컬 원본 DB와 자료는 변경하지 않았습니다.')


if __name__ == '__main__':
    main()
