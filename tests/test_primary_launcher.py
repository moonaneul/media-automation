import importlib.util
from pathlib import Path
from unittest.mock import Mock
import sys


def load():
    path=Path(__file__).resolve().parents[1]/'scripts/start_primary.py'
    spec=importlib.util.spec_from_file_location('primary_launcher',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_launcher_uses_project_root_and_does_not_start_duplicate(tmp_path,monkeypatch):
    from media_automation.web import server
    launcher=load();monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    db=tmp_path/'current.db';db.touch()
    select=Mock(return_value=db);serve=Mock();connection=Mock()
    monkeypatch.setattr(server,'default_database',select)
    monkeypatch.setattr(server,'main',serve)
    monkeypatch.setattr(launcher.socket,'create_connection',Mock(return_value=connection))
    monkeypatch.setattr(sys,'argv',['start_primary.py'])
    launcher.main()
    select.assert_called_once_with(tmp_path)
    connection.close.assert_called_once()
    serve.assert_not_called()


def test_launcher_passes_selected_store_and_single_port(tmp_path,monkeypatch):
    from media_automation.web import server
    launcher=load();monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(launcher,'ROOT',tmp_path)
    db=tmp_path/'current.db';db.touch()
    monkeypatch.setattr(server,'default_database',lambda root:db)
    seen=[]
    monkeypatch.setattr(server,'main',lambda:seen.append(sys.argv.copy()))
    monkeypatch.setattr(launcher.socket,'create_connection',Mock(side_effect=ConnectionRefusedError))
    monkeypatch.setattr(sys,'argv',['start_primary.py'])
    launcher.main()
    assert seen==[['start_primary.py','--port','8876','--database',str(db)]]
