"""Local server with authenticated HTTPS proxy mode; external exposure is configured explicitly."""
import logging
import argparse
import ipaddress
import os
import secrets
import time
import threading
from http.cookies import SimpleCookie
import json
import mimetypes
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from .work_store import WorkStore, RevisionConflict
from .production_order import build_order
from .generation import generate, BUILD_VERSION, SUNDAY_TYPOGRAPHY_VERSION as UI_SUNDAY_VERSION, FRIDAY_TYPOGRAPHY_VERSION as UI_FRIDAY_VERSION
from .bulletin_generation import generate_bulletin, LAYOUT_VERSION as UI_BULLETIN_VERSION
from .notice_files import extract_notice
from .ppt_preview import preview
from ..streaming_download import send_download

UI = Path(__file__).resolve().parent / 'ui'


class BulletinReviewBlocked(ValueError):
    """Safe and actionable reason for refusing a bulletin's review approval."""
    pass

def make_server(store, port=0, password=None, bind_host="127.0.0.1", public_origin=None, supabase_auth=None, hosted=None):
    address = ipaddress.ip_address(bind_host)
    if address.version != 4 or not (address.is_loopback or address.is_private) or (address.is_unspecified and hosted is None):
        raise ValueError("이 컴퓨터의 사설 IPv4 주소만 사용할 수 있습니다.")
    if not address.is_loopback and not supabase_auth and (not password or len(password) < 12):
        raise ValueError("휴대폰 연결에는 12자 이상의 접속 암호가 필요합니다.")
    if public_origin:
        origin = urlsplit(public_origin)
        if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
                or origin.path or origin.query or origin.fragment or origin.port not in (None,443)):
            raise ValueError('배포 접속 주소는 경로 없는 HTTPS 주소여야 합니다.')
        if (not address.is_loopback and hosted is None) or (not supabase_auth and (not password or len(password) < 16)):
            raise ValueError('HTTPS 배포는 내부 서버와 16자 이상의 접속 암호가 필요합니다.')
    if hosted is not None and (not public_origin or not supabase_auth or password):
        raise ValueError('Hosted runtime requires HTTPS and Supabase login')
    cookie_security = '; Secure' if public_origin else ''
    from ...cloud.supabase_auth import AccessDenied, AuthUnavailable
    if supabase_auth and password:
        raise ValueError("Supabase login and shared password cannot be combined")
    sessions={}
    access_tokens={}
    auth_lock=threading.Lock()
    production_lock=threading.Lock()
    from .onedrive import OneDrive
    cloud=hosted.cloud if hosted is not None else OneDrive(store)
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
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(data)

        def route(self):
            if hosted is not None and self.command == 'GET' and self.path == '/healthz':
                return self.reply(200, {'ready': True})
            host = f'{bind_host}:{self.server.server_port}'
            expected_host = urlsplit(public_origin).netloc if public_origin else host
            if not public_origin and bind_host=='127.0.0.1' and self.headers.get('Host')==f'localhost:{self.server.server_port}':
                expected_host=f'localhost:{self.server.server_port}'
            expected_origin = public_origin or 'http://' + expected_host
            if (self.headers.get('Host') != expected_host or self.headers.get('Origin', expected_origin) != expected_origin
                    or public_origin and ((hosted is None and not ipaddress.ip_address(self.client_address[0]).is_loopback)
                                          or self.headers.get('X-Forwarded-Proto') != 'https')):
                return self.reply(403, {'error':'허용된 접속 주소만 이용할 수 있습니다.'})
            if hosted is not None and self.command not in ('GET', 'HEAD') and self.headers.get('Origin') != expected_origin:
                return self.reply(403, {'error':'접속 주소를 확인하세요.'})
            parsed = urlsplit(self.path)
            if self.command == 'GET' and parsed.path in ('/', '/index.html'):
                html=(UI / 'index.html').read_text()
                for marker,version in {'__ENGINE_VERSION__':BUILD_VERSION,'__SUNDAY_VERSION__':UI_SUNDAY_VERSION,'__FRIDAY_VERSION__':UI_FRIDAY_VERSION,'__BULLETIN_VERSION__':UI_BULLETIN_VERSION}.items():html=html.replace(marker,version)
                if hosted is not None:
                    html=html.replace('</body>', '<script src="/cloud-runtime.js"></script></body>')
                return self.reply(200, html.encode(), 'text/html; charset=utf-8')
            if hosted is not None and self.command == 'GET' and parsed.path == '/cloud-runtime.js':
                return self.reply(200, Path(hosted.script).read_bytes(), 'text/javascript; charset=utf-8')
            if self.command == 'GET' and parsed.path == '/onedrive.js':
                return self.reply(200,(UI/'onedrive.js').read_bytes(),'text/javascript; charset=utf-8')
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
                    access_tokens.pop(expired,None)
                authenticated=(not password and not supabase_auth) or token in sessions
                access_token=access_tokens.get(token)
            if hosted is not None:
                try:
                    access_token=hosted.sessions.read(token)
                except AuthUnavailable:
                    return self.reply(503, {'error':'로그인 상태를 확인하지 못했습니다.'})
            member=None
            if supabase_auth:
                authenticated=False
                if access_token:
                    try:
                        member=supabase_auth.authenticate("Bearer " + access_token)
                        authenticated=True
                    except AccessDenied:
                        with auth_lock:
                            sessions.pop(token,None)
                            access_tokens.pop(token,None)
                    except AuthUnavailable:
                        if parsed.path != "/api/logout":
                            return self.reply(503,{"error":"로그인 서버에 연결하지 못했습니다. 잠시 후 다시 시도하세요."})
            if self.command == 'GET' and parsed.path == '/api/mode':
                return self.reply(200, {'hosted':hosted is not None, 'shared':True, 'local_only':address.is_loopback,'password_required':bool(password or supabase_auth),'auth_provider':'supabase' if supabase_auth else 'local','authenticated':authenticated})
            if self.command=='POST' and parsed.path=='/api/login':
                try:
                    if self.headers.get('Content-Type')!='application/json':
                        raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=4096:
                        raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    value=body.get('password')
                    if not isinstance(value,str):
                        raise ValueError()
                    if supabase_auth:
                        with auth_lock:
                            failures[:]=[t for t in failures if t>now-60]
                            if len(failures)>=10:
                                return self.reply(429,{'error':'잠시 후 다시 시도하세요.'})
                        try:
                            access_token=supabase_auth.login(body.get('email'),value)
                        except AccessDenied:
                            with auth_lock: failures.append(now)
                            return self.reply(401,{'error':'이메일·비밀번호 또는 미디어팀 승인 상태를 확인하세요.'})
                        except AuthUnavailable:
                            return self.reply(503,{'error':'로그인 서버에 연결하지 못했습니다.'})
                        if hosted is not None:
                            try:
                                member=supabase_auth.authenticate('Bearer ' + access_token)
                                new_token=hosted.sessions.create(access_token, member)
                                hosted.sessions.delete(token)
                            except (AccessDenied, AuthUnavailable):
                                return self.reply(503, {'error':'로그인 상태 저장에 실패했습니다.'})
                        else:
                            new_token=secrets.token_urlsafe(32)
                        with auth_lock:
                            sessions.pop(token,None)
                            access_tokens.pop(token,None)
                            sessions[new_token]=now+3600
                            access_tokens[new_token]=access_token
                        self.session_cookie='media_session='+new_token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=3600'+cookie_security
                        return self.reply(200,{'authenticated':True})
                    with auth_lock:
                        failures[:]=[t for t in failures if t>now-60]
                        if len(failures)>=10:
                            return self.reply(429,{'error':'잠시 후 다시 시도하세요.'})
                        if password and not secrets.compare_digest(value.encode(),password.encode()):
                            failures.append(now)
                            return self.reply(401,{'error':'공용 비밀번호를 확인하세요.'})
                        new_token=secrets.token_urlsafe(32)
                        sessions[new_token]=now+8*60*60
                    self.session_cookie='media_session='+new_token+'; HttpOnly; SameSite=Strict; Path=/; Max-Age=28800'+cookie_security
                    return self.reply(200,{'authenticated':True})
                except (ValueError,TypeError,AttributeError):
                    return self.reply(400,{'error':'접속 요청을 확인하세요.'})
            if self.command=='POST' and parsed.path=='/api/logout':
                if hosted is not None:
                    try:
                        hosted.sessions.delete(token)
                    except AuthUnavailable:
                        return self.reply(503, {'error':'로그아웃 결과를 확인하지 못했습니다.'})
                with auth_lock:
                    sessions.pop(token,None)
                    access_tokens.pop(token,None)
                self.session_cookie='media_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'+cookie_security
                return self.reply(200,{'authenticated':False})
            if hosted is not None:
                if not authenticated:
                    return self.reply(401, {'error':'로그인 후 이용하세요.'})
                return hosted.handle(self, parsed, access_token, member)
            from .onedrive_http import handle as handle_cloud
            def cloud_session_valid(session_token):
                with auth_lock:
                    return (not password and not supabase_auth) or sessions.get(session_token,0)>time.time()
            if parsed.path.startswith('/api/onedrive/'):
                # Uploads can run for minutes. Do not hold cloud.lock across
                # the HTTP response: it blocks status/diagnostics/retry from
                # other threads. The OneDrive client protects its own state.
                if handle_cloud(cloud,self,parsed,expected_origin,authenticated,token,cloud_session_valid):
                    return
            if not authenticated:
                return self.reply(401,{'error':'로그인 후 이용하세요.'})
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
                        if self.command!='POST' or self.headers.get('Content-Type')!='application/json' or not 0<size<=9*1024*1024:raise ValueError()
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
                        if type(edited.get('reference_year')) is not int or not 2000<=edited['reference_year']<=2100:raise ValueError()
                        if 'cover_photo' in edited:
                            from media_automation.bulletin.cover_photo import photo_bytes
                            photo_bytes(edited['cover_photo'])
                            data['cover_photo']=edited['cover_photo']
                        data['reference_year']=edited['reference_year']
                        data['status']='confirmed'
                        db.execute('INSERT OR REPLACE INTO bulletin_settings VALUES (1,?,?)',(revision+1,json.dumps(data,ensure_ascii=False)))
                        # Keep completed historical files intact; pending PDFs must
                        # be rebuilt when their saved settings differ.
                        for day,work_revision,payload in list(db.execute("SELECT date,revision,payload FROM works WHERE service='sunday'")):
                            work=json.loads(payload);output=work.get('outputs',{}).get('pdf',{})
                            if not output.get('generated') or output.get('complete') or output.get('changed'):continue
                            identifier=output.get('fileId','')
                            if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):continue
                            report_path=Path(store.path).with_suffix('.generated')/(identifier+'.json')
                            if not report_path.is_file():continue
                            report=json.loads(report_path.read_text())
                            if report.get('settings')==data:continue
                            output['changed']=True
                            db.execute("UPDATE works SET revision=?,payload=? WHERE date=? AND service='sunday'",(work_revision+1,json.dumps(work,ensure_ascii=False),day))
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
                    return self.reply(200,extract_notice(filename,content))
                except Exception:
                    return self.reply(400,{'error':'HWP·HWPX 파일을 읽지 못했습니다. 텍스트를 붙여 넣어 주세요.'})
            if self.command=='GET' and parsed.path=='/api/original':
                try:
                    digest=parse_qs(parsed.query)['digest'][0]
                    path, filename=store.original(digest)
                    mime=mimetypes.guess_type(filename)[0]
                    if mime not in ('application/pdf','video/mp4','audio/mpeg','audio/x-wav','audio/wav',
                                    'application/vnd.ms-powerpoint','application/vnd.openxmlformats-officedocument.presentationml.presentation'):
                        return self.reply(415, {'error':'지원하는 원본 파일을 선택하세요.'})
                    return self.reply(200,path.read_bytes(),mime)
                except (ValueError,KeyError,FileNotFoundError):
                    return self.reply(404, {'error':'원본을 찾지 못했습니다.'})
            if self.command=='GET' and parsed.path=='/api/asset-preview':
                try:
                    digest=parse_qs(parsed.query)['digest'][0]
                    path, filename=store.original(digest)
                    from .ppt_conversion import convert_original
                    from media_automation.web.pptx_preview import convert_pptx
                    if Path(filename).suffix.lower()=='.ppt':
                        try:
                            path=convert_original(path)
                        except RuntimeError as error:
                            # Conversion messages are controlled by our converter and safe to show.
                            return self.reply(422, {'error':'구형 악보 변환 실패: '+str(error)})
                    if Path(filename).suffix.lower() not in ('.ppt','.pptx'): raise ValueError('PPT 원본을 선택하세요.')
                    cache=Path(store.path).with_suffix('.previews');cache.mkdir(exist_ok=True)
                    output=cache/(digest+'.pdf')
                    if not output.is_file():convert_pptx(path,output)
                    query=parse_qs(parsed.query)
                    from pypdf import PdfReader
                    count=len(PdfReader(output).pages)
                    if query.get('info')==['1']:return self.reply(200,{'page_count':count})
                    if 'page' in query:
                        page=int(query['page'][0])
                        if not 1<=page<=count:raise ValueError('페이지 번호를 확인하세요.')
                        from .ppt_preview import render_pdf_page
                        png=cache/(digest+f'-{page}.png')
                        return self.reply(200,render_pdf_page(output,page,png),'image/png')
                    return self.reply(200,output.read_bytes(),'application/pdf')
                except Exception:
                    return self.reply(503,{'error':'원본 미리보기를 만들지 못했습니다. 원본 파일을 확인하세요.'})
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
                    from .generation import compatible_original
                    mode=store.get(day,service)['data'].get('fridayMode','zoom')
                    if not compatible_original(query['filename'][0], service, mode, query['slot'][0]):
                        return self.reply(400, {'error':'현재 예배 방식에 맞는 원본을 선택하세요. 대면 찬양은 악보 PPT, Zoom 찬양은 MP4, 배경음악은 MP3입니다.'})
                    return self.reply(201,store.attach(day,service,query['slot'][0],query['filename'][0],content,query.get('song_id',[None])[0]))
                except (ValueError,KeyError):
                    return self.reply(400, {'error':'파일명·지원 형식·예배 항목을 확인하세요.'})
                except Exception:
                    return self.reply(500, {'error':'원본 저장에 실패했습니다. 다시 첨부해 주세요.'})
            if self.command=='POST' and parsed.path=='/api/song-assets':
                try:
                    query=parse_qs(parsed.query)
                    if self.headers.get('Content-Type')!='application/octet-stream':raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=128*1024*1024:return self.reply(413,{'error':'128MB 이하의 파일을 사용하세요.'})
                    content=self.rfile.read(size)
                    if len(content)!=size:raise ValueError()
                    return self.reply(201,store.attach_song_asset(query['song_id'][0],query['filename'][0],content,query.get('replace_digest',[None])[0]))
                except (ValueError,KeyError):return self.reply(400,{'error':'등록 곡과 파일 형식을 확인하세요.'})
                except Exception:return self.reply(500,{'error':'찬양 원본 저장에 실패했습니다.'})
            if self.command=='POST' and parsed.path=='/api/remove-original':
                try:
                    size=int(self.headers.get('Content-Length','-1'))
                    if self.headers.get('Content-Type')!='application/json' or not 0<size<=16384:raise ValueError()
                    return self.reply(200,store.remove_original(json.loads(self.rfile.read(size))))
                except (ValueError,KeyError,TypeError):
                    return self.reply(400,{'error':'삭제할 원본과 예배 항목을 확인하세요.'})
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
            if self.command=='GET' and parsed.path in ('/api/ppt-preview','/api/pdf-preview'):
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
                    'fields':data.get('fields',{}), 'date':data.get('date'),
                    'service':data.get('service'), 'connections':data.get('connections',[]),
                    'background_music':data.get('background_music',[]),
                    'complete':False, 'visual_review_pending':True})
            if self.command in ('GET', 'HEAD') and parsed.path=='/api/generated':
                identifier=parse_qs(parsed.query).get('id',[''])[0]
                if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):
                    return self.reply(400,{'error':'파일을 확인하세요.'})
                extension=parse_qs(parsed.query).get('format',['pptx'])[0]
                if extension not in ('pptx','pdf'):return self.reply(400,{'error':'파일 형식을 확인하세요.'})
                file=Path(store.path).with_suffix('.generated')/(identifier+'.'+extension)
                if not file.is_file():return self.reply(404,{'error':'파일을 찾지 못했습니다.'})
                return send_download(self, file, head_only=self.command=='HEAD')
            if self.command=='POST' and parsed.path=='/api/reopen-ppt-review':
                # Revoking approval affects this PPT's review status only.
                # Neither the generated artifact nor past OneDrive uploads
                # are ever deleted, moved or marked as missing.
                try:
                    size=int(self.headers.get('Content-Length','-1'))
                    if self.headers.get('Content-Type')!='application/json' or not 0<size<=8192:
                        raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    if body.get('confirmed') is not True:
                        raise ValueError()
                    identifier=body.get('file_id','')
                    if not isinstance(identifier,str) or len(identifier)!=32 or any(
                            ch not in '0123456789abcdef' for ch in identifier):
                        raise ValueError()
                    if body.get('service') not in ('sunday','wednesday','friday'):
                        raise ValueError()
                    current=store.get(body['date'],body['service'])
                    ppt=current['data'].get('outputs',{}).get('ppt',{})
                    if (ppt.get('fileId')!=identifier or not ppt.get('complete')
                            or ppt.get('changed')):
                        return self.reply(409,{'error':'해당 PPT의 완료 기록이 변경되었습니다. 최신 상태를 확인하세요.'})
                    ppt['complete']=False
                    ppt['reviewRevokedAt']=datetime.now(timezone.utc).isoformat(timespec='seconds')
                    # Keep cloudItem, cloudVerified, archiveStatus and prior
                    # manual review audit; re-approval must be explicit.
                    saved=store.save(body['date'],body['service'],body['revision'],current['data'])
                    return self.reply(200,saved)
                except RevisionConflict:
                    return self.reply(409,{'error':'다른 화면에서 검수 기록이 변경됐습니다. 새로고침 후 확인하세요.'})
                except Exception:
                    return self.reply(400,{'error':'현재 파일과 검수 완료 기록을 확인한 뒤 다시 시도하세요.'})
            if self.command=='POST' and parsed.path in ('/api/complete-bulletin','/api/complete'):
                try:
                    size=int(self.headers.get('Content-Length','-1'))
                    if self.headers.get('Content-Type')!='application/json' or not 0<size<=8192:raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    if body.get('reviewed') is not True:raise ValueError()
                    identifier=body['file_id']
                    if len(identifier)!=32 or any(c not in '0123456789abcdef' for c in identifier):raise ValueError()
                    directory=Path(store.path).with_suffix('.generated')
                    report=json.loads((directory/(identifier+'.json')).read_text())
                    current=store.get(body['date'],body['service'])
                    if report.get('date')!=body['date'] or report.get('service')!=body['service']:raise ValueError()
                    if report['fields']!=current['data']['fields']:
                        if report.get('format')=='pdf':
                            raise BulletinReviewBlocked('주보 PDF를 만든 뒤 입력이 변경되었습니다. PDF를 다시 제작해 확인하세요.')
                        raise ValueError()
                    bible_receipts={}
                    if report.get('format')=='pdf':
                        if report.get('unresolved'):
                            labels=', '.join(str(name) for name in report['unresolved'][:25])
                            raise BulletinReviewBlocked('주보 PDF 미확정 항목: '+labels+' · 내용을 확정하고 PDF를 다시 제작해 주세요.')
                        from media_automation.bulletin.original_design import LAYOUT_VERSION
                        if report.get('layout_version')!=LAYOUT_VERSION:
                            raise BulletinReviewBlocked('주보 PDF 제작 코드가 갱신되었습니다. 최신 코드로 PDF를 다시 제작해 주세요.')
                        if not (directory/(identifier+'.pdf')).is_file():
                            raise BulletinReviewBlocked('생성된 주보 PDF 파일이 없습니다. PDF를 다시 제작해 주세요.')
                        with store.connect() as db:
                            row=db.execute('SELECT payload FROM bulletin_settings WHERE id=1').fetchone()
                        settings=json.loads(row[0]) if row else json.loads((UI.parent/'bulletin-base-reference.json').read_text())
                        if report.get('settings')!=settings:
                            raise BulletinReviewBlocked('주보 기본 설정이 PDF 제작 후 변경되었습니다. PDF를 다시 제작해 주세요.')
                    else:
                        unresolved=report.get('unresolved',[])
                        if not isinstance(unresolved,list) or any(not isinstance(x,str) for x in unresolved):raise ValueError()
                        acknowledged=[x for x in unresolved if x.endswith((':score_asset', ':audio_asset', ':original_review', ':bible_review'))]
                        manual_reviews=[x for x in acknowledged if x.endswith((':original_review', ':bible_review'))]
                        if (len(acknowledged)!=len(unresolved) or body.get('acknowledged_unresolved',[])!=acknowledged
                                or body.get('confirmed_manual_reviews',[])!=manual_reviews):raise ValueError()
                        from .generation import render_configuration, _asset, SUNDAY_TYPOGRAPHY_VERSION, FRIDAY_TYPOGRAPHY_VERSION
                        if body['service'] in ('sunday','wednesday') and report.get('typography_version')!=SUNDAY_TYPOGRAPHY_VERSION:raise ValueError()
                        if body['service']=='friday' and report.get('typography_version')!=FRIDAY_TYPOGRAPHY_VERSION:raise ValueError()
                        if report.get('render_configuration')!=render_configuration(current['data']):raise ValueError()
                        if report.get('attachments')!=store.attachments(body['date'],body['service']):raise ValueError()
                        if not (directory/(identifier+'.pptx')).is_file():raise ValueError()
                        # Only a freshly generated PPT with source digests
                        # can seed reusable manual review receipts. Historic
                        # complete=True records cannot be promoted silently.
                        pending=report.get('bible_review_digests',{})
                        if pending:
                            if not isinstance(pending,dict):raise ValueError()
                            from .bible_connection import resolve
                            from .bible_review_cache import units_for_manual_confirmation
                            labels=[name for name in manual_reviews if name.endswith(':bible_review')]
                            blocks=[]
                            expected={}
                            for label in labels:
                                slot=label[:-len(':bible_review')]
                                stored=pending.get(slot)
                                if stored is None:
                                    continue # supporting-prayer verse: no exact source receipt
                                if not isinstance(stored,dict):raise ValueError()
                                expected.update(stored)
                                field=current['data']['fields'].get(slot,{})
                                if field.get('state')!='VALUE' or not field.get('value'):
                                    raise ValueError()
                                blocks.append(dict(kind='input',key=slot,state='VALUE',
                                                   content=field['value']))
                            if blocks:
                                candidate=units_for_manual_confirmation(resolve(blocks),labels)
                                if candidate!=expected:
                                    raise BulletinReviewBlocked(
                                        '검수할 성경 본문이 PPT 제작 시 사용한 원문과 달라졌습니다. 정확한 자료로 다시 제작하세요.')
                                bible_receipts=candidate
                        for slot, connected in report.get('connections',{}).items():
                            if connected.get('status')!='connected':continue
                            text=current['data']['fields'].get(slot,{}).get('value','')
                            selected=_asset(store,body,{'key':slot,'content':text})
                            if not selected or selected[2]['digest']!=connected['digest']:raise ValueError()
                    data=current['data'];kind='pdf' if report['format']=='pdf' else 'ppt';o=data['outputs'][kind]
                    if o.get('fileId')!=identifier or o.get('changed'):
                        if kind=='pdf':
                            raise BulletinReviewBlocked('현재 선택한 파일이 최신 주보 PDF가 아닙니다. PDF를 다시 제작해 주세요.')
                        raise ValueError()
                    # Re-reviewing an already approved file must never
                    # invalidate an existing OneDrive archive record.
                    previous_archive=o.get('archiveStatus')
                    has_cloud_item=bool(o.get('cloudItem'))
                    new_status=(previous_archive if kind=='ppt' and has_cloud_item
                                else 'pending_connection')
                    o.update(complete=True,changed=False,archiveStatus=new_status,
                             acknowledgedUnresolved=acknowledged if kind=='ppt' else [],
                             confirmedManualReviews=manual_reviews if kind=='ppt' else [])
                    if kind=='ppt':
                        o['reviewedAt']=datetime.now(timezone.utc).isoformat(timespec='seconds')
                        o.pop('reviewRevokedAt',None)
                    saved=store.save(body['date'],body['service'],body['revision'],data)
                    if kind=='ppt' and bible_receipts:
                        # A human explicitly checked all verses at approval.
                        # Store exact hashes, not copyrighted verse text.
                        store.record_bible_review_receipts(
                            bible_receipts,date=body['date'],
                            service=body['service'],file_id=identifier)
                    return self.reply(200,saved)
                except BulletinReviewBlocked as exc:
                    return self.reply(409, {'error':str(exc)})
                except RevisionConflict:
                    return self.reply(409, {'error':'다른 화면에서 예배 입력이나 완료 상태가 변경됐습니다. 최신 상태를 확인해 주세요.'})
                except Exception:return self.reply(400,{'error':'최신 제작 파일과 입력·자료 변경을 확인하고 다시 검수하세요.'})
            if self.command=='POST' and parsed.path=='/api/build':
                output_label = 'PPT'
                try:
                    if self.headers.get('Content-Type')!='application/json':raise ValueError()
                    size=int(self.headers.get('Content-Length','-1'))
                    if not 0<size<=1024*1024:raise ValueError()
                    body=json.loads(self.rfile.read(size))
                    if not isinstance(body,dict):raise ValueError('제작 요청 형식을 확인하세요.')
                    output_label = '주보 PDF' if body.get('output')=='pdf' else 'PPT'
                    if not production_lock.acquire(blocking=False):
                        return self.reply(409, {'error':'다른 제작이 진행 중입니다. 완료 후 다시 제작하세요.'})
                    try:
                        result = generate_bulletin(store,body) if body.get('output')=='pdf' else generate(store,body)
                    finally:
                        production_lock.release()
                    return self.reply(200,result)
                except (ValueError,KeyError,TypeError) as exc:return self.reply(400,{'error':str(exc) or '입력과 저장 상태를 확인하세요.'})
                except Exception:
                    logging.exception('%s generation failed',output_label)
                    return self.reply(500,{'error':output_label+' 생성에 실패했습니다. 실행 중인 서버 터미널의 오류 내용을 확인하세요. 입력은 유지됩니다.'})
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
        do_HEAD = route
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
