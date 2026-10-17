import importlib.util
import json
from pathlib import Path
import re
import sqlite3

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/export_supabase_works.py'
spec = importlib.util.spec_from_file_location('exporter', SCRIPT)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)
UID = '776e30f7-9dd3-4229-b9d4-23de72331f21'


def create_database(path, payload):
    with sqlite3.connect(path) as db:
        db.execute('create table works(date text,service text,revision integer,payload text,updated_at text)')
        db.execute('insert into works values(?,?,?,?,?)', ('2026-10-14', 'wednesday', 7,
                   json.dumps(payload, ensure_ascii=False), '2026-10-14T01:02:03+00:00'))
        db.execute('create table migration_work_history(source text)')
        db.execute('insert into migration_work_history values (?)', ('old-source',))


def test_payload_and_revision_round_trip_without_changing_source(tmp_path):
    source = tmp_path / 'source.db'
    payload = {'fields': {'설교 제목': {'state': 'VALUE', 'value': "ADMIN DATA COUNT TAG BLOCK '$$' \\ 본문"}}}
    create_database(source, payload)
    before = source.read_bytes()
    target = tmp_path / 'migration.sql'
    report = exporter.export(source, target, UID)
    sql = target.read_text()
    match = re.search(r'v_rows jsonb := \$(media_data_[a-f0-9]+)\$(.*?)\$\1\$::jsonb;', sql, re.S)
    records = json.loads(match.group(2))
    assert records[0]['payload'] == payload
    assert records[0]['revision'] == 7
    assert records[0]['updated_at'] == '2026-10-14T01:02:03+00:00'
    assert report['count'] == 1
    assert source.read_bytes() == before
    with sqlite3.connect(target.with_suffix('.sqlite3')) as backup:
        assert backup.execute('select count(*) from migration_work_history').fetchone()[0] == 1


def test_reexport_does_not_overwrite_existing_file(tmp_path):
    source = tmp_path / 'source.db'
    create_database(source, {})
    target = tmp_path / 'migration.sql'
    exporter.export(source, target, UID)
    before = target.read_bytes()
    with pytest.raises(ValueError):
        exporter.export(source, target, UID)
    assert target.read_bytes() == before


def test_invalid_admin_or_missing_source_fails_before_export(tmp_path):
    with pytest.raises(ValueError):
        exporter.export(tmp_path / 'missing.db', tmp_path / 'x.sql', 'invalid')
    with pytest.raises(ValueError):
        exporter.export(tmp_path / 'missing.db', tmp_path / 'x.sql', UID)
    assert not (tmp_path / 'x.sql').exists()
