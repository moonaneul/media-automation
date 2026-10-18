#!/usr/bin/env python3
"""Diagnose real, content-addressed score files without changing the church DB.

Only a disposable copy inside the system temp directory is converted.  No web,
OneDrive, Supabase or production endpoint is called. No worship field is edited.
"""
import argparse
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
from shutil import copyfile

from pptx import Presentation
from media_automation.web.original.ppt_conversion import convert_original


def read_rows(database, words):
    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as db:
        candidates = []
        for table, sql in (
            ('attachments', 'SELECT day,service,slot,filename,digest FROM attachments'),
            ('song_assets', 'SELECT song_id,filename,digest FROM song_assets'),
        ):
            try:
                for row in db.execute(sql):
                    name = row[-2]
                    if not name.lower().endswith(('.ppt', '.pptx')): continue
                    if words and not any(word.casefold() in name.casefold() for word in words): continue
                    descriptor = ('/'.join(str(x) for x in row[:3]) if table == 'attachments'
                                  else '자료실 곡 원본')
                    candidates.append((name, row[-1], descriptor))
            except sqlite3.OperationalError:
                pass
        reports = []
        try:
            for day, service, payload in db.execute('SELECT date,service,payload FROM works'):
                data = json.loads(payload)
                output = data.get('outputs', {}).get('ppt', {})
                if output.get('fileId'):
                    reports.append((day, service, output['fileId']))
        except sqlite3.OperationalError:
            pass
    unique = []
    digests = set()
    for name, digest, descriptor in candidates:
        key=(digest,name)
        if key in digests: continue
        digests.add(key)
        unique.append((name,digest,descriptor))
    return unique, reports


def probe_file(db_path, name, digest):
    from zipfile import BadZipFile
    stored = db_path.with_suffix('.files') / digest
    print(f'  원본 존재: {"예" if stored.is_file() else "아니오"}')
    if not stored.is_file():
        print('  판정: 원본 파일이 없어서 삽입할 수 없습니다. 복사된 DB의 .files 연결을 확인해야 합니다.')
        return
    correct = hashlib.sha256(stored.read_bytes()).hexdigest() == digest
    print('  원본 식별값 일치:', '예' if correct else '아니오')
    if not correct:
        print('  판정: 원본 파일 식별값이 등록 기록과 다릅니다.')
        return
    signature = stored.read_bytes()[:8]
    kind = '실제 구형 OLE PPT' if signature.startswith(bytes.fromhex('D0CF11E0')) else (
        'PPTX ZIP 구조' if signature.startswith(b'PK') else '기타/알 수 없는 구조')
    print('  내부 형식:', kind)
    with tempfile.TemporaryDirectory(prefix='media-score-probe-') as temp:
        source=Path(temp)/('original' + Path(name).suffix.lower())
        copyfile(stored, source)
        try:
            if source.suffix == '.ppt':
                converted=convert_original(source)
            else:
                converted=source
            deck=Presentation(converted)
            count=len(deck.slides)
            size=(deck.slide_width/914400, deck.slide_height/914400)
            landscape=abs(size[0]-10) <= 12700/914400 and abs(size[1]-7.5) <= 12700/914400
            print(f'  변환/읽기: 성공 · {count}장 · {size[0]:.3f} × {size[1]:.3f}인치')
            if not landscape:
                print('  주의: 기본 수요/주일 10 × 7.5인치와 크기가 다릅니다.')
                print('        실제 템플릿과 크기가 다르면 슬라이드 병합 단계에서 거부됩니다.')
            else:
                print('  기본 4:3 크기 비교: 일치')
        except Exception as error:
            print('  변환/읽기: 실패')
            detail=str(error).replace(str(source),'(임시원본)').replace(str(Path(temp)), '(임시폴더)')
            print('  실패 원인:', detail[:400] or error.__class__.__name__)


def report_generated(database, saved):
    folder=database.with_suffix('.generated')
    print('\n최근 예배 출력 기록 (저장 DB와 파일 연결만 확인):')
    if not saved:
        print('  출력 기록 없음')
        return
    for date,svc,ident in sorted(saved,reverse=True)[:6]:
        file=folder/(ident+'.pptx')
        report=folder/(ident+'.json')
        print(' ',date,svc,'PPT 파일', '존재' if file.is_file() else '없음',
              '제작 보고서', '존재' if report.is_file() else '없음')
        if report.is_file():
            try:
                raw=json.loads(report.read_text())
                for item in raw.get('mapping',[]):
                    if item.get('kind') != 'song': continue
                    connection=raw.get('connections',{}).get(item.get('key'),{})
                    if item.get('status')=='original_inserted':continue
                    print('     ',item.get('key'),':',item.get('status'),'/',
                          connection.get('status','원본 없음'),connection.get('error','')[:140])
            except (ValueError,OSError,AttributeError):
                print('      제작 보고서를 읽을 수 없습니다.')


def main():
    parser=argparse.ArgumentParser(description='악보 .ppt 변환/삽입 원인 진단 · DB 및 원본 수정 안 함')
    parser.add_argument('database',type=Path)
    parser.add_argument('--match',action='append',default=[],help='파일명 일부 (여러 번 지정 가능)')
    parser.add_argument('--limit',type=int,default=8)
    args=parser.parse_args()
    database=args.database.expanduser().resolve()
    if not database.is_file(): parser.error('검수용 DB를 찾지 못했습니다.')
    print('악보 원본 진단 · 원본 DB/파일·OneDrive 변경 없음')
    print('DB:',database)
    candidates,reports=read_rows(database,args.match)
    print('대상:',len(candidates),'개 (최대',args.limit,'개 변환 진단)')
    for name,digest,descriptor in candidates[:max(0,args.limit)]:
        print('\n['+descriptor+']',name)
        probe_file(database,name,digest)
    report_generated(database,reports)


if __name__=='__main__':
    main()
