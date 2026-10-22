"""Read-only completion diagnostics must not expose weekly values or alter files."""
import json
import sqlite3

from scripts.inspect_worship_completion import inspect


def test_inspect_outputs_states_without_mutating_or_printing_values(tmp_path, capsys):
    database=tmp_path/"work.db"
    private_value="CONFIDENTIAL_EXAMPLE_NAME_DO_NOT_PRINT"
    data={
        "fields":{"설교자":{"state":"UNSET","value":""},"교회 소식":{"state":"VALUE","value":private_value}},
        "outputs":{
            "ppt":{"generated":True,"complete":True,"changed":False,"archiveStatus":"uploaded"},
            "pdf":{"generated":True,"complete":False,"changed":False,"archiveStatus":""}
        },
    }
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE works(date TEXT,service TEXT,revision INTEGER,payload TEXT)")
        db.execute("INSERT INTO works VALUES (?,?,?,?)",
                   ("2026-10-18","sunday",7,json.dumps(data,ensure_ascii=False)))
    before=database.read_bytes()
    assert inspect(database,"2026-10-18")==0
    printed=capsys.readouterr().out
    assert "검수완료=True" in printed
    assert "검수완료=False" in printed
    assert private_value not in printed
    assert database.read_bytes()==before


def test_inspect_missing_db_does_not_create_file(tmp_path, capsys):
    database=tmp_path/"missing.db"
    assert inspect(database,"2026-10-18")==2
    assert not database.exists()
    assert "ERROR" in capsys.readouterr().out
