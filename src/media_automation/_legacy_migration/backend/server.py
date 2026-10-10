"""Loopback-only integration server. Online hosting and authentication are not enabled."""
import argparse
import ipaddress
import os
import secrets
import time
import threading
from http.cookies import SimpleCookie
import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from work_store import WorkStore, RevisionConflict
from production_order import build_order
from generation import generate
from bulletin_generation import generate_bulletin
from notice_files import extract_notice
from ppt_preview import preview

UI = Path(__file__).resolve().parent.parent / 'ui'

def make_server(store, port=0, password=None, bind_host="127.0.0.1"):
    address = ipaddress.ip_address(bind_host)
    if address.version != 4 or not (address.is_loopback or address.is_private) or address.is_unspecified:
        raise ValueError("이 컴퓨터의 사설 IPv4 주소만 사용할 수 있습니다.")
    if not address.is_loopback and (not password or len(password) < 12):
        raise ValueError("휴대폰 연결에는 12자 이상의 접속 암호가 필요합니다.")
    sessions={}
    auth_lock=threading.Lock()
    failures=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, status, body, mime='application/json; charset=utf-8'):
            data = json.dumps(body, ensure_ascii=False).encode() if not isinstance(body, bytes) else body
            self.send_response(status)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            if getattr(self,'session_cookie',None):
                self.send_header('Set-Cookie',self.session_cookie)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        def route(self):
            host = f'{bind_host}:{self.server.server_port}'
            if self.headers.get('Host') != host or self.headers.get('Origin', 'http://' + host) != 'http://' + host:
                return self.reply(403, {'error':'로컬 연결만 이용할 수 있습니다.'})
            parsed = urlsplit(self.path)
            if self.command == 'GET' and parsed.path in ('/', '/index.html'):
                return self.reply(200, (UI / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            if self.command == 'GET' and parsed.path == '/bulletin-number.js':
                return self.reply(200,(UI/'bulletin-number.js').read_bytes(),'text/javascript; charset=utf-8')
            if self.command == 'GET' and parsed.path == '/notice-parser.js':
                return self.reply(200,(UI/'notice-parser.js').read_bytes(),'text/javascript; charset=utf-8')
            if self.command == 'GET' and parsed.path == '/song-search.js':
                return self.reply(200, (UI / 'song-search.js').read_bytes(), 'text/javascript; charset=utf-8')
            cookie=SimpleCookie()
            try:
                cookie.load(self.headers.get('Cookie',''))
                token=cookie['media_session'].value if 'media_session' in cookie else ''
            except Exception:
                token=''
            now=time.time()
            with auth_lock:
                for expired in [key for key,value in sessions.items() if value<=now]:
                    sessions.pop(expired,None)
                authenticated=not password or token in sessions
            if self.command == 'GET' and parsed.path == '/api/mode':
                return self.reply(200, {'shared':True, 'local_only':address.is_loopback,'password_required':bool(password),'authenticated':authenticated})
            if self.command=='POST' and parsed.path=='/api/login':
                try:
                    if self.headers.get('Content-Type')!='application/json':
                        raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=4096:
                        raise ValueError()
                    value=json.loads(self.rfile.read(size)).get('password')
                    if not isinstance(value,str):
                        raise ValueError()
                    with auth_lock:
                        failures[:]=[t for t in failures if t>now-60]
                        if len(failures)>=10:
                            return self.reply(429,{'error':'잠시 후 다시 시도하세요.'})
                        if password and not secrets.compare_digest(value.encode(),password.encode()):
                            failures.append(now)
                            return self.reply(401,{'error':'공용 비밀번호를 확인하세요.'})
                        new_token=secrets.token_urlsafe(32)
                        sessions[new_token]=now+8*60*60
                    self.session_cookie='media_session='+new_token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'
                    return self.reply(200,{'authenticated':True})
                except (ValueError,TypeError,AttributeError):
                    return self.reply(400,{'error':'접속 요청을 확인하세요.'})
            if self.command=='POST' and parsed.path=='/api/logout':
                with auth_lock:
                    sessions.pop(token,None)
                self.session_cookie='media_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'
                return self.reply(200,{'authenticated':False})
            if not authenticated:
                return self.reply(401,{'error':'공용 비밀번호로 접속하세요.'})
            if parsed.path=='/api/bulletin-settings':
                try:
                    with store.connect() as db:
                        db.execute('CREATE TABLE IF NOT EXISTS bulletin_settings (id INTEGER PRIMARY KEY, revision INTEGER, payload TEXT)')
                        db.execute('BEGIN IMMEDIATE')
                        row=db.execute('SELECT revision,payload FROM bulletin_settings WHERE id=1').fetchone()
                        revision=row[0] if row else 0
                        data=json.loads(row[1]) if row else json.loads((UI.parent/'bulletin-base-reference.json').read_text())
                        if self.command=='GET':return self.reply(200,{'revision':revision,'data':data})
                        size=int(self.headers.get('Content-Length','-1'))
                        if self.command!='POST' or self.headers.get('Content-Type')!='application/json' or not 0<size<=65536:raise ValueError()
                        incoming=json.loads(self.rfile.read(size))
                        if incoming['revision']!=revision:return self.reply(409,{'error':'다른 화면에서 설정이 바뀌었습니다. 다시 불러와 확인하세요.'})
                        edited=incoming['data']
                        for group in ('annual','church','meeting_times'):
                            if set(edited[group])!=set(data[group]):raise ValueError()
                            for key,value in edited[group].items():
                                if isinstance(data[group][key],list):
                                    if not isinstance(value,list) or len(value)>30 or any(not isinstance(v,str) or len(v)>2000 for v in value):raise ValueError()
                                elif not isinstance(value,str) or len(value)>5000:raise ValueError()
                            data[group]=edited[group]
                        db.execute('INSERT OR REPLACE INTO bulletin_settings VALUES (1,?,?)',(revision+1,json.dumps(data,ensure_ascii=False)))
                    return self.reply(200,{'revision':revision+1,'data':data})
                except Exception:return self.reply(400,{'error':'주보 설정 내용을 확인하세요.'})
            if self.command=='POST' and parsed.path=='/api/notice-file':
                try:
                    if self.headers.get('Content-Type')!='application/octet-stream':raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=8*1024*1024:return self.reply(413,{'error':'안내 파일은 8MB 이하로 첨부하세요.'})
                    filename=parse_qs(parsed.query)['filename'][0]
                    content=self.rfile.read(size)
                    if len(content)!=size:raise ValueError()
                    return self.reply(200,{'text':extract_notice(filename,content),'filename':filename})
                except Exception:
                    return self.reply(400,{'error':'HWP·HWPX 파일을 읽지 못했습니다. 텍스트를 붙여 넣어 주세요.'})
            if self.command=='GET' and parsed.path=='/api/original':
                try:
                    digest=parse_qs(parsed.query)['digest'][0]
                    path, filename=store.original(digest)
                    mime=mimetypes.guess_type(filename)[0]
                    if mime not in ('application/pdf','video/mp4','audio/mpeg','audio/x-wav','audio/wav'):
                        return self.reply(415, {'error':'PPT 원본 미리보기는 렌더링 연결 후 제공됩니다.'})
                    return self.reply(200,path.read_bytes(),mime)
                except (ValueError,KeyError,FileNotFoundError):
                    return self.reply(404, {'error':'원본을 찾지 못했습니다.'})
            if self.command=='GET' and parsed.path=='/api/background-music':
                try:
                    role=parse_qs(parsed.query)['role'][0]
                    directory=Path(__file__).with_name('static')/'friday-background-music'
                    asset=json.loads((directory/'manifest.json').read_text())['assets'][role]
                    return self.reply(200,(directory/asset['filename']).read_bytes(),'audio/mpeg')
                except (KeyError,FileNotFoundError):
                    return self.reply(404,{'error':'기본 배경음악을 찾지 못했습니다.'})
            if parsed.path == '/api/attachments':
                try:
                    query=parse_qs(parsed.query)
                    day, service=query['date'][0],query['service'][0]
                    if self.command=='GET':
                        return self.reply(200, {'attachments':store.attachments(day,service)})
                    if self.headers.get('Content-Type')!='application/octet-stream':
                        raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=128*1024*1024:
                        return self.reply(413, {'error':'첨부는 128MB 이하의 파일을 사용하세요.'})
                    content=self.rfile.read(size)
                    if len(content)!=size:
                        raise ValueError()
                    return self.reply(201,store.attach(day,service,query['slot'][0],query['filename'][0],content,query.get('song_id',[None])[0]))
                except (ValueError,KeyError):
                    return self.reply(400, {'error':'파일명·지원 형식·예배 항목을 확인하세요.'})
                except Exception:
                    return self.reply(500, {'error':'원본 저장에 실패했습니다. 다시 첨부해 주세요.'})
            if self.command=='POST' and parsed.path=='/api/asset-review':
                try:
                    if self.headers.get('Content-Type')!='application/json':
                        raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=16384:
                        raise ValueError()
                    data=json.loads(self.rfile.read(size))
                    return self.reply(200,store.review_asset(data['song_id'],data['digest'],data['review']))
                except (ValueError,KeyError,TypeError):
                    return self.reply(400, {'error':'등록 자료와 확인 상태를 점검하세요.'})
            if parsed.path == '/api/songs':
                if self.command == 'GET':
                    return self.reply(200, {'songs': store.songs()})
                try:
                    if self.headers.get('Content-Type') != 'application/json':
                        raise ValueError()
                    size = int(self.headers.get('Content-Length', '-1'))
                    if not 0 < size <= 16384:
                        raise ValueError()
                    data = json.loads(self.rfile.read(size))
                    if not isinstance(data, dict):
                        raise ValueError()
                    return self.reply(201, store.register_song(data))
                except (ValueError, TypeError):
                    return self.reply(400, {'error':'곡명·찬송가 종류·번호를 확인하세요.'})
            if self.command=='GET' and parsed.path=='/api/ppt-preview':
                try:
                    query=parse_qs(parsed.query)
                    return self.reply(200,preview(store,query.get('id',[''])[0],int(query.get('page',['1'])[0])),'image/png')
                except ValueError:
                    return self.reply(400,{'error':'파일과 슬라이드 번호를 확인하세요.'})
                except FileNotFoundError:
                    return self.reply(404,{'error':'PPT 파일을 찾지 못했습니다.'})
                except Exception:
                    return self.reply(503,{'error':'이 슬라이드의 미리보기를 만들지 못했습니다. PPT를 내려받아 확인하세요.'})
            if self.command=='GET' and parsed.path=='/api/generated-report':
                identifier=parse_qs(parsed.query).get('id',[''])[0]
                if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):
                    return self.reply(400,{'error':'파일을 확인하세요.'})
                directory=Path(store.path).with_suffix('.generated')
                report=directory/(identifier+'.json')
                if not report.is_file() or not (directory/(identifier+'.pptx')).is_file():
                    return self.reply(404,{'error':'PPT 제작 결과를 찾지 못했습니다.'})
                data=json.loads(report.read_text())
                return self.reply(200,{'slide_count':data['slide_count'],'mapping':[
                    {key:item.get(key) for key in ('key','kind','start','end','status')}
                    for item in data.get('mapping',[])], 'unresolved':data.get('unresolved',[]),
                    'visual_review_pending':True})
            if self.command=='GET' and parsed.path=='/api/generated':
                identifier=parse_qs(parsed.query).get('id',[''])[0]
                if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):
                    return self.reply(400,{'error':'파일을 확인하세요.'})
                extension=parse_qs(parsed.query).get('format',['pptx'])[0]
                if extension not in ('pptx','pdf'):return self.reply(400,{'error':'파일 형식을 확인하세요.'})
                file=Path(store.path).with_suffix('.generated')/(identifier+'.'+extension)
                if not file.is_file():return self.reply(404,{'error':'파일을 찾지 못했습니다.'})
                return self.reply(200,file.read_bytes(),'application/pdf' if extension=='pdf' else 'application/vnd.openxmlformats-officedocument.presentationml.presentation')
            if self.command=='POST' and parsed.path=='/api/complete-bulletin':
                try:
                    size=int(self.headers.get('Content-Length','-1'))
                    if self.headers.get('Content-Type')!='application/json' or not 0<size<=8192:raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    if body['service']!='sunday' or body.get('reviewed') is not True:raise ValueError()
                    identifier=body['file_id']
                    if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError()
                    directory=Path(store.path).with_suffix('.generated')
                    report=json.loads((directory/(identifier+'.json')).read_text())
                    current=store.get(body['date'],'sunday')
                    if report.get('format')!='pdf' or report['unresolved'] or report['fields']!=current['data']['fields']:raise ValueError()
                    data=current['data'];o=data['outputs']['pdf']
                    if o.get('fileId')!=identifier or o.get('changed'):raise ValueError()
                    o.update(complete=True,changed=False,archiveStatus='pending_connection')
                    saved=store.save(body['date'],'sunday',body['revision'],data)
                    return self.reply(200,saved)
                except Exception:return self.reply(400,{'error':'최신 PDF와 입력 누락을 확인하고 다시 검수하세요.'})
            if self.command=='POST' and parsed.path=='/api/build':
                try:
                    if self.headers.get('Content-Type')!='application/json':raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=1024*1024:raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    return self.reply(200,generate_bulletin(store,body) if body.get('output')=='pdf' else generate(store,body))
                except (ValueError,KeyError,TypeError):return self.reply(400,{'error':'입력과 저장 상태를 확인하세요.'})
                except Exception:return self.reply(500,{'error':'PPT 생성에 실패했습니다. 입력은 유지됩니다.'})
            if self.command=='POST' and parsed.path=='/api/production-order':
                try:
                    if self.headers.get('Content-Type')!='application/json':raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=1024*1024:raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    current=store.get(body['date'],body['service'])
                    if current['revision']!=body['revision']:
                        return self.reply(409,{'error':'다른 화면의 변경을 확인한 뒤 제작하세요.'})
                    order=build_order(body['groups'],current['data'].get('fields',{}),body['service'])
                    return self.reply(200,{'order':order,'revision':current['revision'],'file_generated':False})
                except (ValueError,KeyError,TypeError):
                    return self.reply(400,{'error':'제작 순서와 저장 상태를 확인하세요.'})
            if parsed.path != '/api/work':
                return self.reply(404, {'error':'없는 경로입니다.'})
            try:
                query = parse_qs(parsed.query)
                day, service = query['date'][0], query['service'][0]
                if self.command == 'GET':
                    return self.reply(200, store.get(day, service))
                if self.headers.get('Content-Type') != 'application/json':
                    return self.reply(415, {'error':'JSON 입력이 필요합니다.'})
                size = int(self.headers.get('Content-Length', '-1'))
                if not 0 < size <= 1024 * 1024:
                    return self.reply(413, {'error':'입력 크기를 확인하세요.'})
                body = json.loads(self.rfile.read(size))
                self.reply(200, store.save(day, service, body['revision'], body['data']))
            except RevisionConflict as exc:
                self.reply(409, {'error':str(exc), 'current':exc.current})
            except (ValueError, KeyError, TypeError):
                self.reply(400, {'error':'입력 형식을 확인하세요.'})
            except Exception:
                self.reply(500, {'error':'공동 저장에 실패했습니다.'})

        do_GET = route
        do_PUT = route
        do_POST = route
    return ThreadingHTTPServer((bind_host,port), Handler)

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=18766)
    parser.add_argument('--database',type=Path,default=Path(__file__).with_name('work.db'))
    args=parser.parse_args()
    server=make_server(WorkStore(args.database),args.port,os.environ.get('MEDIA_ACCESS_PASSWORD'))
    print(f'로컬 연결 검증: http://127.0.0.1:{server.server_port}/',flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
