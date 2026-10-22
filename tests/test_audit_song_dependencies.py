"""Read-only legacy-song reference report must not mutate existing tables."""
import runpy
from pathlib import Path

from media_automation.web.original.work_store import WorkStore


def test_reference_audit_reports_saved_usage_without_mutating(tmp_path, capsys):
    store = WorkStore(tmp_path / "work.db")
    song = store.register_song({"title": "cover"})
    digest = "a" * 64
    with store.connect() as db:
        db.execute("INSERT INTO song_assets VALUES (?,?,?)", (song["id"], digest, "cover.pptx"))
        db.execute("INSERT INTO attachments VALUES (?,?,?,?,?)",
                   ("2026-10-14", "wednesday", "특별 자료", "cover.pptx", digest))
    store.save("2026-10-14", "wednesday", 0, {
        "fields": {},
        "songChoices": {"시작 찬양 1": song["id"]},
        "assetChoices": {"시작 찬양 1": digest},
    })
    script = Path(__file__).resolve().parents[1] / "scripts" / "audit_song_dependencies.py"
    report = runpy.run_path(str(script))["audit"]
    report(tmp_path / "work.db")
    printed = capsys.readouterr().out
    assert "의심 곡 수: 1" in printed
    assert "저장된 예배 입력 직접 참조: 2" in printed
    assert "예배 원본 첨부의 동일 파일 참조: 1" in printed
    assert "변경하지 않았습니다" in printed
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM song_assets").fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM works").fetchone()[0] == 1
