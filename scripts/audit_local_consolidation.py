"""Read-only comparison of local work folders and church application stores."""
import argparse
import json
import sqlite3
import subprocess
from pathlib import Path


def read_store(path):
    path = Path(path).resolve()
    with sqlite3.connect(path.as_uri() + '?mode=ro', uri=True) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if 'works' not in tables:
            raise ValueError('예배 작업 DB가 아닙니다.')
        works = {(day, service): json.loads(payload) for day, service, payload in
                 db.execute('SELECT date, service, payload FROM works')}
        # Compare semantic content, not revisions or modification timestamps.
        extras = {}
        for table in ('attachments', 'songs', 'song_assets', 'asset_reviews', 'bulletin_settings'):
            if table in tables:
                extras[table] = set(db.execute('SELECT * FROM "' + table + '"'))
        return works, extras


def compare_stores(main, other):
    left, left_extra = read_store(main)
    right, right_extra = read_store(other)
    changes = []
    for key in sorted(left.keys() | right.keys()):
        if key not in left:
            changes.append((key, '이 DB에만 있음', []))
        elif key not in right:
            changes.append((key, 'main에만 있음', []))
        elif left[key] != right[key]:
            a, b = left[key], right[key]
            fields_a, fields_b = a.get('fields', {}), b.get('fields', {})
            fields = [label for label in sorted(fields_a.keys() | fields_b.keys())
                      if fields_a.get(label) != fields_b.get(label)]
            metadata = [name for name in sorted(a.keys() | b.keys()) if name != 'fields'
                        and a.get(name) != b.get(name)]
            changes.append((key, '내용 차이', fields + ['설정:' + name for name in metadata]))
    extras = {table: (len(left_extra.get(table, set()) - right_extra.get(table, set())),
                      len(right_extra.get(table, set()) - left_extra.get(table, set())))
              for table in left_extra.keys() | right_extra.keys()
              if left_extra.get(table, set()) != right_extra.get(table, set())}
    return len(right), changes, extras


def git(root, *args):
    result = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True)
    return result.returncode, result.stdout.strip()


def audit_folder(root, main):
    print('\n폴더:', root)
    code, top = git(root, 'rev-parse', '--show-toplevel')
    if code or Path(top).resolve() != root.resolve():
        print('  독립 Git 작업 폴더 아님 · 삭제 여부는 아직 판단하지 않습니다.')
        return
    _, status = git(root, '-c', 'core.quotePath=false', 'status', '--short', '--branch')
    print(status or '  변경 없음')
    _, head = git(root, 'log', '-1', '--format=%h %s')
    print('  현재 커밋:', head)
    # The explicit main checkout determines the comparison commit. Do not silently
    # use a possibly stale origin/main in a separate checkout.
    _, main_sha = git(main, 'rev-parse', 'HEAD')
    code, commits = git(root, 'log', '--oneline', main_sha + '..HEAD', '--', 'src', 'scripts', 'tests', 'docs', 'webapp.py')
    if code:
        print('  main 비교 커밋이 이 저장소에 없음 · 별도 확인 필요')
    elif commits:
        print('  main에 포함되지 않은 코드 커밋 이력 (최종 내용 차이는 별도 확인):')
        print(commits)
    else:
        print('  main 밖의 코드 커밋 이력 없음')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--main', required=True, type=Path)
    parser.add_argument('--review', required=True, type=Path)
    parser.add_argument('--original', required=True, type=Path)
    args = parser.parse_args()
    primary = args.main.expanduser().resolve()
    pointer = primary / 'output/main-database.txt'
    database = Path(pointer.read_text().strip()).expanduser().resolve()
    print('비교 기준 main 폴더:', primary)
    print('실사용 DB:', database)
    works, _ = read_store(database)
    print('실사용 예배:', len(works))
    candidates = {primary, args.review.expanduser().resolve(), args.original.expanduser().resolve()}
    candidates.update(p.resolve() for p in primary.parent.glob('media-automation*') if p.is_dir())
    _, worktrees = git(primary, 'worktree', 'list', '--porcelain')
    for line in worktrees.splitlines():
        if line.startswith('worktree '):
            candidates.add(Path(line[9:]).resolve())
    for root in sorted(candidates):
        if not root.is_dir():
            print('\n폴더 없음:', root)
            continue
        audit_folder(root, primary)
        for path in sorted((root / 'output').rglob('*.db')):
            if path.resolve() == database:
                continue
            print('  비교 DB:', path)
            try:
                count, changes, extras = compare_stores(database, path)
                print('    예배:', count, '· 차이:', len(changes))
                for (day, service), kind, labels in changes:
                    print('   ', day, service, kind, ' / '.join(labels))
                for table, (main_only, other_only) in sorted(extras.items()):
                    print('   ', table, 'main에만:', main_only, '이 DB에만:', other_only)
                if not changes and not extras:
                    print('    예배·자료 목록 동일')
            except (sqlite3.Error, ValueError, OSError) as error:
                print('    비교 불가:', error)
    print('\n읽기 전용 점검 완료 · DB, 파일, 브랜치는 변경하지 않았습니다.')


if __name__ == '__main__':
    main()
