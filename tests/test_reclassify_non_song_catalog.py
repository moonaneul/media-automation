"""Safe, explicit local-only reclassification of legacy non-song records."""
import json
import runpy
from pathlib import Path
import sqlite3

import pytest
from media_automation.web.original.work_store import WorkStore


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "reclassify_non_song_catalog.py"


def prepare_legacy(tmp_path):
    store = WorkStore(tmp_path / "source.db")
    song = store.register_song({"title": "cover"})
    digest = "a" * 64
    with store.connect() as db:
        db.execute("INSERT INTO song_assets VALUES (?,?,?)",
                   (song['id'], digest, "cover_abc123.pptx"))
        db.execute("CREATE TABLE cloud_auto_sources (item_id TEXT PRIMARY KEY, song_id TEXT, stamp TEXT, digest TEXT)")
        db.execute("INSERT INTO cloud_auto_sources VALUES (?,?,?,?)",
                   ("drive-item", song['id'], "test:1", digest))
        db.execute("CREATE TABLE cloud_song_sources (song_id TEXT, digest TEXT, drive_item TEXT, PRIMARY KEY(song_id,digest))")
        db.execute("INSERT INTO cloud_song_sources VALUES (?,?,?)",
                   (song['id'], digest, "drive-item"))
    return store, song, digest


def test_copy_keeps_cloud_mapping_and_original_unchanged(tmp_path):
    store, song, digest = prepare_legacy(tmp_path)
    apply = runpy.run_path(str(SCRIPT))['reclassify_copy']
    result = tmp_path / "classified.db"
    preview = apply(store.path, None, [song['id']])
    assert preview[0]['role'] == 'bulletin'
    assert not result.exists()
    apply(store.path, result, [song['id']])
    with sqlite3.connect(result) as db:
        assert db.execute("SELECT COUNT(*) FROM songs").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM song_assets").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM cloud_auto_sources").fetchone()[0] == 0
        assert db.execute("SELECT COUNT(*) FROM cloud_song_sources").fetchone()[0] == 0
        role, payload = db.execute(
            "SELECT role,payload FROM classified_originals WHERE original_song_id=?",
            (song['id'],)).fetchone()
        archived = json.loads(payload)
        assert role == 'bulletin'
        assert archived['assets'][0]['digest'] == digest
        assert archived['cloud_auto_sources'][0]['item_id'] == 'drive-item'
        assert archived['cloud_song_sources'][0]['drive_item'] == 'drive-item'
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM songs").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM cloud_auto_sources").fetchone()[0] == 1


def test_refuses_used_song_without_creating_copy(tmp_path):
    store, song, _ = prepare_legacy(tmp_path)
    store.save('2026-10-14','wednesday',0, {
        'fields': {}, 'songChoices': {'찬양 1': song['id']}
    })
    output = tmp_path / "should-not-be-created.db"
    with pytest.raises(ValueError, match='예배 입력'):
        runpy.run_path(str(SCRIPT))['reclassify_copy'](store.path, output, [song['id']])
    assert not output.exists()


def test_refuses_unclassified_or_same_input_copy(tmp_path):
    store, song, _ = prepare_legacy(tmp_path)
    migrate = runpy.run_path(str(SCRIPT))['reclassify_copy']
    with pytest.raises(ValueError, match='원본과 다르고'):
        migrate(store.path, store.path, [song['id']])
    with pytest.raises(ValueError, match='존재하지 않는'):
        migrate(store.path, tmp_path / 'other.db', ['nonexistent'])
