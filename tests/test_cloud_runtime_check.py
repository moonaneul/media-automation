import importlib.util
from pathlib import Path
from types import SimpleNamespace


def load():
    path=Path(__file__).resolve().parents[1]/'src/media_automation/cloud/runtime_check.py'
    spec=importlib.util.spec_from_file_location('runtime_check',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_linux_tools_and_font_are_required(monkeypatch):
    check=load()
    monkeypatch.setattr(check.platform,'system',lambda:'Linux')
    monkeypatch.setattr(check.importlib,'import_module',lambda name:object())
    monkeypatch.setattr(check.shutil,'which',lambda name:'/bin/'+name)
    monkeypatch.setattr(check.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='Noto Sans CJK KR'))
    assert check.inspect_runtime()['ready'] is True
    monkeypatch.setattr(check.shutil,'which',lambda name:None if name=='soffice' else '/bin/'+name)
    assert check.inspect_runtime()['ready'] is False


def test_fallback_font_is_not_accepted_and_no_secrets_reported(monkeypatch):
    check=load()
    monkeypatch.setattr(check.platform,'system',lambda:'Linux')
    monkeypatch.setattr(check.importlib,'import_module',lambda name:object())
    monkeypatch.setattr(check.shutil,'which',lambda name:'/bin/'+name)
    monkeypatch.setattr(check.subprocess,'run',lambda *a,**k:SimpleNamespace(returncode=0,stdout='DejaVu Sans'))
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY','must-not-appear')
    result=check.inspect_runtime()
    assert not result['ready'] and not result['korean_font']
    assert 'must-not-appear' not in str(result)
