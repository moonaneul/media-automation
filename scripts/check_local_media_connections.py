"""Read-only inventory of the resources used by local review servers."""
import argparse
import sqlite3
from pathlib import Path


def inspect_project(root):
    root=Path(root).expanduser().resolve()
    print('\n작업 폴더:',root)
    for label,relative in [
        ('성경 JSON','data/private/bible_fixed.json'),
        ('검수 본문','data/private/bible_sources'),
        ('시작 화면','assets/worship'),
        ('금요 원본 디자인','assets/private/friday_reference'),
        ('금요 배경음악','assets/private/friday_zoom'),
    ]:
        path=root/relative
        count=sum(1 for p in path.rglob('*') if p.is_file()) if path.is_dir() else int(path.is_file())
        print(f'{label}: {count}개 · {path}')
    for relative in ('output/web','output/unified-work','output/original-blue'):
        folder=root/relative
        if folder.is_dir():
            for path in sorted(folder.glob('*.db')):
                inspect_database(path)


def inspect_database(path):
    path=Path(path).expanduser().resolve()
    print('DB:',path)
    if not path.is_file():
        print('  없음');return
    try:
        with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as db:
            tables={row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if 'works' in tables:
                print('  저장된 예배:',db.execute('SELECT COUNT(*) FROM works').fetchone()[0])
            if 'attachments' in tables:
                print('  첨부:',dict(db.execute('SELECT service,COUNT(*) FROM attachments GROUP BY service')))
    except sqlite3.Error as error:
        print('  읽기 실패:',error)
    folder=path.with_suffix('.files')
    print('  첨부 파일 폴더:',folder,'·',sum(1 for p in folder.glob('*') if p.is_file()),'개')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',action='append',default=[])
    parser.add_argument('--database',action='append',default=[])
    args=parser.parse_args()
    for root in args.project:inspect_project(root)
    for path in args.database:inspect_database(path)
