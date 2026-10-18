#!/usr/bin/env python3
"""Read-only reference audit for legacy non-song rows in a local SQLite work DB.

Reports whether a suspicious catalog song is still referenced by saved worship
work, attachments, or cloud mapping rows. Never modifies or uploads anything.
Does not inspect OneDrive itself or the Cloud Run Supabase catalog.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from media_automation.web.original.original_roles import original_role, song_candidate  # noqa: E402


def walk(value, path=()):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from walk(item, (*path, str(key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk(item, (*path, str(index)))
    elif isinstance(value, str):
        yield path, value


def audit(database):
    database = Path(database).expanduser().resolve()
    if not database.is_file():
        raise ValueError("작업 DB를 찾지 못했습니다.")
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"songs", "song_assets", "works"}.issubset(tables):
            raise ValueError("예배 및 찬양 테이블이 없습니다.")

        assets = list(db.execute("SELECT song_id,digest,filename FROM song_assets"))
        by_song = {}
        for song_id, digest, filename in assets:
            by_song.setdefault(song_id, []).append((digest, filename))
        suspects = []
        for identifier, payload in db.execute("SELECT id,payload FROM songs ORDER BY rowid"):
            song = json.loads(payload)
            title = song.get("title", "")
            marked_title = original_role(title + ".pptx") not in ("score", "song_video", "audio_candidate")
            marked_files = [(digest, name) for digest, name in by_song.get(identifier, [])
                            if not song_candidate(name)]
            if marked_title or marked_files:
                suspects.append((identifier, title, by_song.get(identifier, [])))

        works = [(day, service, json.loads(payload))
                 for day, service, payload in db.execute("SELECT date,service,payload FROM works")]
        attachments = list(db.execute("SELECT day,service,slot,digest FROM attachments")) if "attachments" in tables else []
        reviews = list(db.execute("SELECT song_id,digest FROM asset_reviews")) if "asset_reviews" in tables else []
        cloud = {}
        for table in ("cloud_auto_sources", "cloud_song_sources"):
            if table in tables:
                columns = [c[1] for c in db.execute("PRAGMA table_info(" + table + ")")]
                if "song_id" in columns and "digest" in columns:
                    cloud[table] = list(db.execute("SELECT song_id,digest FROM " + table))

        print("찬양 외 등록 항목 참조 점검 · 읽기 전용")
        print("의심 곡 수:", len(suspects))
        for identifier, title, attached_assets in suspects:
            digests = {digest for digest, _ in attached_assets}
            print("\n[분류 재검토]", title, "| 곡 ID:", identifier)
            print("기존 등록 파일:", ", ".join(filename for _, filename in attached_assets) or "없음")
            matches = []
            for day, service, data in works:
                for keys, value in walk(data):
                    if value == identifier or value in digests:
                        matches.append((day, service, ".".join(keys)[:150], "곡" if value == identifier else "파일"))
            print("저장된 예배 입력 직접 참조:", len(matches))
            for day, service, place, kind in matches[:15]:
                print("  -", day, service, kind, place)
            if len(matches) > 15:
                print("  - 추가 참조가 있어 일부만 표시합니다.")
            other = [(day, service, slot) for day, service, slot, digest in attachments if digest in digests]
            print("예배 원본 첨부의 동일 파일 참조:", len(other))
            for day, service, slot in other[:10]:
                print("  -", day, service, slot)
            linked_reviews = sum(song_id == identifier for song_id, _ in reviews)
            print("검수 기록:", linked_reviews)
            for table, rows in cloud.items():
                print(table + " 연결 기록:", sum(song_id == identifier or digest in digests
                                                  for song_id, digest in rows))
        print("\n주의: 참조가 없더라도 클라우드 DB, OneDrive 실제 파일,")
        print("기본 주보·예배 템플릿 사용 여부는 이 검사로 판단할 수 없습니다.")
        print("어떠한 파일, 등록 정보, 예배 입력도 변경하지 않았습니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database")
    args = parser.parse_args()
    try:
        audit(args.database)
    except (ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.exit(2, "점검 실패: " + str(exc) + "\n")
