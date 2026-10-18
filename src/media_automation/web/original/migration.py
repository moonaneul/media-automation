"""Explicit read-only snapshot import of an existing original application store."""
from pathlib import Path
import shutil
import sqlite3
import tempfile
import os


def snapshot_store(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError('기존 저장소를 덮어쓰지 않는 새 경로가 필요합니다.')
    if not source.is_file():raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as folder:
        staged=Path(folder)/destination.name
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as old:
            tables={r[0] for r in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not {'works','songs','attachments'}.issubset(tables):
                raise ValueError('원본 웹 저장소 형식이 아닙니다.')
            with sqlite3.connect(staged) as new:old.backup(new)
        for suffix in ('.files','.generated','.onedrive'):
            original=source.with_suffix(suffix)
            if original.is_dir():
                if destination.with_suffix(suffix).exists():raise FileExistsError(destination.with_suffix(suffix))
                shutil.copytree(original,staged.with_suffix(suffix))
        # Copy before publishing DB, so partial assets can never become active.
        for suffix in ('.files','.generated','.onedrive'):
            copied=staged.with_suffix(suffix)
            if copied.is_dir():os.replace(copied,destination.with_suffix(suffix))
        os.replace(staged,destination)
    return destination


def merge_stores(primary, supplemental, destination_directory, *, keep_primary_works=()):
    """Publish a new store atomically; explicit work conflicts are archived in DB.

    No source is modified. Unknown table conflicts and differing file collisions
    abort the entire merge instead of choosing a winner silently.
    """
    import hashlib
    import json
    primary, supplemental = Path(primary).resolve(), Path(supplemental).resolve()
    target = Path(destination_directory).resolve()
    if target.exists():
        raise FileExistsError('새 통합 저장소 폴더가 필요합니다.')
    target.parent.mkdir(parents=True, exist_ok=True)
    allowed = {tuple(key) for key in keep_primary_works}
    report = {'imported': {}, 'archived_work_conflicts': [], 'file_counts': {}}
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        staged = Path(temp)/'merged'
        staged.mkdir()
        result = staged/'work.db'
        snapshot_store(primary, result)
        with sqlite3.connect(result) as new, sqlite3.connect(supplemental.as_uri()+'?mode=ro', uri=True) as old:
            new.execute('CREATE TABLE IF NOT EXISTS migration_work_history (source TEXT, day TEXT, service TEXT, revision INTEGER, payload TEXT, updated_at TEXT, PRIMARY KEY(source,day,service))')
            tables = list(old.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"))
            for table, schema in tables:
                if table not in {'works','songs','attachments','song_assets','asset_reviews','bulletin_settings','bible_review_receipts'}:
                    raise ValueError('검토되지 않은 저장소 표: '+table)
                new.execute(schema.replace('CREATE TABLE ', 'CREATE TABLE IF NOT EXISTS ', 1))
                info = list(old.execute('PRAGMA table_info("'+table+'")'))
                new_info = list(new.execute('PRAGMA table_info("'+table+'")'))
                if [(r[1],r[2],r[5]) for r in info] != [(r[1],r[2],r[5]) for r in new_info]:
                    raise ValueError('저장소 구조가 다릅니다: '+table)
                keys = [r[1] for r in sorted(info,key=lambda r:r[5]) if r[5]]
                if not keys:raise ValueError('고유 키가 없는 저장소 표: '+table)
                indexes = [next(i for i,r in enumerate(info) if r[1]==k) for k in keys]
                where = ' AND '.join('"'+k+'"=?' for k in keys)
                count = 0
                for row in old.execute('SELECT * FROM "'+table+'"'):
                    key = tuple(row[i] for i in indexes)
                    current = new.execute('SELECT * FROM "'+table+'" WHERE '+where,key).fetchone()
                    if current is None:
                        new.execute('INSERT INTO "'+table+'" VALUES ('+','.join('?' for _ in row)+')',row);count+=1
                    elif current != row:
                        if table != 'works' or key not in allowed:
                            raise ValueError('충돌 확인이 필요합니다: '+table+' '+str(key))
                        new.execute('INSERT INTO migration_work_history VALUES (?,?,?,?,?,?)',(str(supplemental),*row))
                        report['archived_work_conflicts'].append(list(key))
                report['imported'][table] = count
            for suffix in ('.files','.generated'):
                original = supplemental.with_suffix(suffix)
                dest = result.with_suffix(suffix)
                count = 0
                if original.is_dir():
                    for source in original.rglob('*'):
                        if source.is_symlink():raise ValueError('자료의 심볼릭 링크를 확인하세요.')
                        if not source.is_file():continue
                        file = dest/source.relative_to(original)
                        if file.exists():
                            def digest(p):
                                with p.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
                            if digest(source)!=digest(file):raise ValueError('같은 파일명에 다른 자료가 있습니다: '+str(source.relative_to(original)))
                        else:
                            file.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,file);count+=1
                report['file_counts'][suffix] = count
            # Validate each active attachment and generated output before publication.
            for digest, in new.execute('SELECT digest FROM attachments UNION SELECT digest FROM song_assets'):
                file=result.with_suffix('.files')/digest
                if not file.is_file():raise ValueError('첨부 원본이 없습니다: '+digest)
                with file.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=digest:raise ValueError('첨부 파일 해시가 다릅니다.')
            for payload, in new.execute('SELECT payload FROM works'):
                for output in json.loads(payload).get('outputs',{}).values():
                    if output.get('generated') and output.get('fileId'):
                        ident=output['fileId'];fmt=output.get('format','pptx')
                        if not (result.with_suffix('.generated')/(ident+'.'+fmt)).is_file():
                            raise ValueError('제작 산출물이 없습니다: '+ident)
            if new.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('저장소 무결성 확인 실패')
        (staged/'merge-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        os.replace(staged,target)
    return target/'work.db', report
