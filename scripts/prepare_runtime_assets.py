"""Preserve common designs and validated Bible files in OneDrive for cloud jobs."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT / 'scripts'))
from media_automation.web.original.onedrive import OneDrive, public_item, valid_id
from upload_missing_sources import upload_new


def files():
    roots = ['assets/worship', 'assets/private/friday_reference', 'assets/private/friday_zoom',
             'data/private/bible_sources']
    result = [p for name in roots for p in (ROOT / name).rglob('*')
              if p.is_file() and not p.is_symlink() and p.suffix.lower() in {'.pptx', '.mp3', '.json', '.yaml', '.yml'}]
    fixed = ROOT / 'data/private/bible_fixed.json'
    if fixed.is_file(): result.append(fixed)
    return sorted(result)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--database', type=Path, required=True)
    parser.add_argument('--additions', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text()) if args.report.exists() else {'assets': [], 'errors': []}
    done = {r['path'] for r in report['assets']}
    with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        known = dict(db.execute('select digest,drive_item from cloud_song_sources'))
    for row in json.loads(args.additions.read_text())['files']:
        if not row.get('verified_sha256'): raise ValueError('Unverified source')
        known[row['sha256']] = row['item']['id']
    cloud = OneDrive(SimpleNamespace(path=str(args.database)))
    source = cloud.selected('source')
    name = '제작 공통 자료'
    matches = [i for i in cloud.children(source['id']) if i.get('name') == name]
    if matches:
        if len(matches) != 1 or 'folder' not in matches[0]: raise ValueError('Common folder conflict')
        folder = matches[0]
    else:
        folder = cloud.graph('/me/drive/items/' + valid_id(source['id']) + '/children', method='POST',
                             body={'name': name, 'folder': {}, '@microsoft.graph.conflictBehavior': 'fail'})
    for path in files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in done: continue
        try:
            sha = digest(path)
            created = False
            if sha in known:
                item = cloud.item(known[sha])
                if item.get('size') != path.stat().st_size or not cloud.within(item, source):
                    raise ValueError('Existing original reference differs')
                item = public_item(item)
            else:
                item, created = upload_new(cloud, folder, path, path.name, sha)
                known[sha] = item['id']
            report['assets'].append({'path': relative, 'digest': sha, 'filename': path.name,
                                     'size': path.stat().st_size, 'item': item, 'created': created})
            print('공통 자료 확인:', relative, flush=True)
        except Exception:
            report['errors'].append({'path': relative})
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
            print('공통 자료 준비 중단. 비밀 정보는 출력하지 않았습니다.', flush=True)
            return 1
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('공통 자료 연결:', len(report['assets']), flush=True)
    return 0


if __name__ == '__main__': raise SystemExit(main())
