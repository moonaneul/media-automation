#!/usr/bin/env python3
"""Prepare a separate DB copy with manually approved non-song registrations reclassified.

Source is ALWAYS read-only. Original bytes, OneDrive files and live DB stay intact.
By default only print a plan. With --output, create a NEW independent DB file.
For each explicitly approved one-file legacy song record, preserve the complete
song/asset/review/OneDrive provenance in classified_originals and remove only the
stale song registration in the NEW copy.

This intentionally does NOT migrate the independent Cloud Run/Supabase catalog.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.web.original.original_roles import original_role, song_candidate  # noqa: E402

KNOWN_SONG_TABLES = {'song_assets', 'asset_reviews', 'cloud_auto_sources', 'cloud_song_sources'}


def rows(db, table, song_id):
    if table not in {item[0] for item in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
        return []
    columns = [item[1] for item in db.execute('PRAGMA table_info("' + table + '")')]
    if 'song_id' not in columns:
        return []
    return [dict(record) for record in db.execute('SELECT * FROM "' + table + '" WHERE song_id=?', (song_id,))]


def leaves(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from leaves(item)
    elif isinstance(value, list):
        for item in value:
            yield from leaves(item)
    elif isinstance(value, str):
        yield value


def plan(db, identifiers):
    db.row_factory = sqlite3.Row
    present = {item[0] for item in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'songs', 'song_assets', 'works'}.issubset(present):
        raise ValueError('필요한 자료실 및 예배 테이블을 찾지 못했습니다.')
    if len(identifiers) != len(set(identifiers)):
        raise ValueError('중복된 곡 ID가 있습니다.')
    works = [json.loads(item[0]) for item in db.execute('SELECT payload FROM works')]
    attachment_digests = ({item[0] for item in db.execute('SELECT digest FROM attachments')}
                          if 'attachments' in present else set())
    other_tables = []
    for table in present - KNOWN_SONG_TABLES - {'songs'}:
        if not table.replace('_', '').isalnum():
            continue
        if 'song_id' in [item[1] for item in db.execute('PRAGMA table_info("' + table + '")')]:
            other_tables.append(table)

    approved = []
    for identifier in identifiers:
        row = db.execute('SELECT payload FROM songs WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise ValueError('존재하지 않는 곡 ID: ' + identifier)
        song = json.loads(row[0])
        assets = rows(db, 'song_assets', identifier)
        if len(assets) != 1:
            raise ValueError('파일이 정확히 하나인 오등록 항목만 재분류할 수 있습니다: ' + identifier)
        original = assets[0]
        if song_candidate(original['filename']):
            raise ValueError('찬양 원본일 수 있어 자동 재분류를 중단합니다: ' + original['filename'])
        kind = original_role(original['filename'])
        if kind in ('other', 'audio_candidate', 'score', 'song_video'):
            raise ValueError('자료 종류가 불명확해 자동 재분류할 수 없습니다: ' + original['filename'])
        digest = original['digest']
        if any(identifier in set(leaves(work)) or digest in set(leaves(work)) for work in works):
            raise ValueError('예배 입력이 해당 곡/원본을 참조하여 변경할 수 없습니다: ' + song['title'])
        if digest in attachment_digests:
            raise ValueError('예배 첨부가 해당 원본을 참조하여 변경할 수 없습니다: ' + song['title'])
        for table in other_tables:
            if rows(db, table, identifier):
                raise ValueError('알 수 없는 외부 참조 테이블이 존재합니다: ' + table)

        metadata = {
            'original_song_id': identifier,
            'role': kind,
            'song_payload': song,
            'assets': assets,
            'reviews': rows(db, 'asset_reviews', identifier),
            'cloud_auto_sources': rows(db, 'cloud_auto_sources', identifier),
            'cloud_song_sources': rows(db, 'cloud_song_sources', identifier),
        }
        approved.append(metadata)
    return approved


def reclassify_copy(source, output, ids):
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise ValueError('검사할 SQLite DB가 없습니다.')
    if output is not None:
        output = Path(output).expanduser().resolve()
        if output == source or output.exists():
            raise ValueError('원본과 다르고 아직 존재하지 않는 새 결과 DB 경로를 지정하세요.')
        if not output.parent.is_dir():
            raise ValueError('새 결과 DB의 상위 폴더가 없습니다.')

    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original:
        intended = plan(original, ids)
        print('분류 이동 계획 (원본 DB와 OneDrive 파일 변경 없음)')
        for entry in intended:
            print(' -', entry['song_payload']['title'], '→', entry['role'],
                  '| OneDrive 연결:', len(entry['cloud_auto_sources']) + len(entry['cloud_song_sources']))
        if output is None:
            print('검사만 완료했습니다. --output이 없으므로 결과 DB를 만들지 않았습니다.')
            return intended
        try:
            # Original remains read-only: copy via SQLite's online backup API.
            with sqlite3.connect(output) as destination:
                original.backup(destination)
                # Check copied state again before rewriting registration.
                reviewed = plan(destination, ids)
                if reviewed != intended:
                    raise ValueError('복사 중 DB 내용이 변경되어 안전을 위해 중단합니다.')
                destination.execute('BEGIN IMMEDIATE')
                destination.execute('''CREATE TABLE IF NOT EXISTS classified_originals (
                    original_song_id TEXT PRIMARY KEY,
                    role TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    classified_at TEXT NOT NULL
                )''')
                for entry in intended:
                    identifier = entry['original_song_id']
                    if destination.execute('SELECT 1 FROM classified_originals WHERE original_song_id=?',
                                           (identifier,)).fetchone():
                        raise ValueError('이미 분류된 곡 ID입니다: ' + identifier)
                    destination.execute('INSERT INTO classified_originals VALUES (?,?,?,?)',
                        (identifier, entry['role'], json.dumps(entry, ensure_ascii=False),
                         datetime.now(timezone.utc).isoformat()))
                    for table in KNOWN_SONG_TABLES:
                        if table in {item[0] for item in destination.execute(
                                "SELECT name FROM sqlite_master WHERE type='table'")}:
                            destination.execute('DELETE FROM "' + table + '" WHERE song_id=?', (identifier,))
                    result = destination.execute('DELETE FROM songs WHERE id=?', (identifier,))
                    if result.rowcount != 1:
                        raise ValueError('삭제 대상 등록 상태가 변경되었습니다: ' + identifier)
                destination.commit()
            output.chmod(0o600)
        except Exception:
            output.unlink(missing_ok=True)
            raise
        print('복사본 분류 완료:', output)
        print('원본 DB/OneDrive 파일/실제 예배 데이터는 변경하지 않았습니다.')
        return intended


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database', help='검수할 기존 로컬 작업 DB 경로')
    parser.add_argument('--song-id', action='append', required=True,
                        help='검증된 오등록 곡 ID, 항목별로 반복 입력')
    parser.add_argument('--output', type=Path,
                        help='안전한 신규 SQLite 결과 DB 경로. 생략 시 읽기 전용 계획 표시')
    args = parser.parse_args()
    try:
        reclassify_copy(args.database, args.output, args.song_id)
    except (ValueError, sqlite3.Error, json.JSONDecodeError) as error:
        parser.exit(2, '재분류 중단: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
