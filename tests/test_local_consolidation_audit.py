import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('audit', Path('scripts/audit_local_consolidation.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def make_store(path, payload, revision=1):
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE works(date,service,payload,revision)')
        db.execute('INSERT INTO works VALUES (?,?,?,?)', ('2026-10-14','wednesday',json.dumps(payload),revision))
        db.execute('CREATE TABLE attachments(day,service,slot,digest)')


def test_audit_reports_cancel_choice_and_field_change_without_modifying_db(tmp_path):
    main, review = tmp_path/'main.db', tmp_path/'review.db'
    make_store(main, {'fields':{'기도 담당자':{'state':'VALUE','value':'원문 이름'}}})
    make_store(review, {'fields':{'기도 담당자':{'state':'NONE','value':''}},'assetChoices':{'찬양':'NONE'}})
    before = (main.read_bytes(), review.read_bytes())
    count, changes, extras = audit.compare_stores(main,review)
    assert count == 1 and changes[0][2] == ['기도 담당자','설정:assetChoices']
    assert extras == {}
    assert before == (main.read_bytes(),review.read_bytes())


def test_audit_ignores_revision_and_json_key_order_but_finds_attachment_difference(tmp_path):
    main, review = tmp_path/'main.db', tmp_path/'review.db'
    make_store(main, {'fields':{},'outputs':{}}, 2)
    make_store(review, {'outputs':{},'fields':{}}, 7)
    with sqlite3.connect(review) as db:
        db.execute('INSERT INTO attachments VALUES (?,?,?,?)',('2026-10-14','wednesday','찬양','digest'))
    count, changes, extras = audit.compare_stores(main,review)
    assert not changes and extras['attachments'] == (0,1)


def test_readonly_audit_does_not_create_missing_database(tmp_path):
    missing = tmp_path/'absent.db'
    with pytest.raises(sqlite3.OperationalError):
        audit.read_store(missing)
    assert not missing.exists()
