from pathlib import Path
import pytest
from media_automation.web.server import default_database


def test_selected_main_store_wins_over_older_defaults(tmp_path, monkeypatch):
    monkeypatch.delenv('MEDIA_DATABASE', raising=False)
    selected = tmp_path/'output/main-store/work.db'
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b'existing-store')
    old = tmp_path/'output/unified-work/work.db'
    old.parent.mkdir()
    old.write_bytes(b'older-store')
    (tmp_path/'output/main-database.txt').write_text('output/main-store/work.db\n')
    assert default_database(tmp_path) == selected
    assert selected.read_bytes() == b'existing-store'


@pytest.mark.parametrize('value', ['', 'output/missing/work.db'])
def test_broken_pointer_does_not_silently_create_a_new_store(tmp_path, monkeypatch, value):
    monkeypatch.delenv('MEDIA_DATABASE', raising=False)
    (tmp_path/'output').mkdir()
    (tmp_path/'output/main-database.txt').write_text(value)
    with pytest.raises(ValueError):default_database(tmp_path)
    assert not (tmp_path/'output/web').exists()


def test_explicit_environment_override_and_legacy_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv('MEDIA_DATABASE', '~/chosen.db')
    assert default_database(tmp_path) == Path.home()/'chosen.db'
    monkeypatch.delenv('MEDIA_DATABASE')
    assert default_database(tmp_path) == tmp_path/'output/web/work.db'
    p=tmp_path/'output/unified-work/work.db'
    p.parent.mkdir(parents=True);p.touch()
    assert default_database(tmp_path) == p
