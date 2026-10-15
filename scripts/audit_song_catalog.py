#!/usr/bin/env python3
"""Read-only audit of song catalog entries; never repairs or uploads files.

Usage:
  python scripts/audit_song_catalog.py /path/to/work.db
The audit reports suspicious song-title/file registrations for manual review.
It cannot inspect Supabase/Cloud Run catalog or verify file contents/permissions.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.web.original.original_roles import original_role, song_candidate  # noqa: E402


def audit(db_path):
    db_path = Path(db_path).expanduser().resolve()
    if not db_path.is_file():
        raise ValueError('작업 DB 파일을 찾지 못했습니다.')
    with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as connection:
        tables = {row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if not {'songs', 'song_assets'}.issubset(tables):
            raise ValueError('필요한 찬양 자료실 테이블이 없습니다.')
        songs = [(identifier, json.loads(payload)) for identifier, payload in connection.execute(
            'SELECT id,payload FROM songs ORDER BY rowid')]
        assets = list(connection.execute(
            'SELECT song_id,filename FROM song_assets ORDER BY song_id,filename'))

    suspects = []
    title_only = []
    for identifier, song in songs:
        title = str(song.get('title', '')).strip()
        # A song's title is not a filename, so only flag explicit known
        # non-song labels for MANUAL review. Never remove a record by name.
        tentative = original_role(title + '.pptx')
        if tentative not in ('score', 'song_video', 'audio_candidate'):
            title_only.append((identifier, title, tentative))
    for song_id, filename in assets:
        if not song_candidate(filename):
            suspects.append((song_id, filename, original_role(filename)))

    print('찬양 자료실 읽기 전용 분류 점검')
    print('등록 곡:', len(songs))
    print('등록 원본 관계:', len(assets))
    print('확인할 비찬양 파일 연결:', len(suspects))
    print('확인할 곡명:', len(title_only))
    print('※ 파일과 DB를 변경하지 않았습니다. 이 결과만으로 자동 삭제·이동하지 마세요.')
    for song_id, filename, kind in suspects[:40]:
        print('[원본 분류 확인]', kind, '|', filename, '| 곡 ID:', song_id)
    for song_id, title, kind in title_only[:40]:
        print('[곡명 분류 확인]', kind, '|', title, '| 곡 ID:', song_id)
    if len(suspects) > 40 or len(title_only) > 40:
        print('일부 결과만 표시했습니다. 전체 데이터는 DB 원본을 유지한 채 검토하세요.')
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', help='SQLite 작업 DB 파일 위치 (읽기 전용)')
    args = parser.parse_args()
    try:
        raise SystemExit(audit(args.database))
    except (ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        parser.exit(2, '점검 실패: ' + str(exc) + '\n')
