"""HTTP adapter for OneDrive; OAuth callback uses its own bound browser cookie."""
import secrets
from http.cookies import SimpleCookie
from urllib.parse import parse_qs
from .onedrive import CloudError, CALLBACK


def handle(cloud, handler, parsed, origin, authenticated, session_token, session_valid):
    if not parsed.path.startswith('/api/onedrive/'):
        return False
    cookie_security = '; Secure' if origin.startswith('https:') else ''
    try:
        if parsed.path == CALLBACK and handler.command == 'GET':
            cookie = SimpleCookie()
            cookie.load(handler.headers.get('Cookie',''))
            binding = cookie['media_cloud'].value if 'media_cloud' in cookie else ''
            query = parse_qs(parsed.query)
            if any(len(v)!=1 for v in query.values()) or len(parsed.query)>16384:
                raise CloudError('Microsoft 로그인 응답을 확인하세요.')
            cloud.finish({k:v[0] for k,v in query.items()}, binding, session_valid)
            handler.send_response(303)
            handler.send_header('Location','/?onedrive=connected')
            handler.send_header('Cache-Control','no-store')
            handler.send_header('Referrer-Policy','no-referrer')
            handler.send_header('Set-Cookie','media_cloud=; HttpOnly; SameSite=Lax; Path=/api/onedrive/; Max-Age=0'+cookie_security)
            handler.send_header('Content-Length','0')
            handler.end_headers()
            return True
        if not authenticated:
            handler.reply(401,{'error':'공용 비밀번호로 접속하세요.'})
            return True
        query = parse_qs(parsed.query)
        def argument(key,default=''):
            values = query.get(key,[default])
            if len(values)!=1:
                raise CloudError('요청 항목을 확인하세요.')
            return values[0]
        body={}
        if handler.command=='POST':
            import json
            size=int(handler.headers.get('Content-Length','-1'))
            if handler.headers.get('Content-Type')!='application/json' or not 0<size<=16384:
                raise CloudError('연결 요청 내용을 확인하세요.')
            body=json.loads(handler.rfile.read(size))
            if not isinstance(body,dict):
                raise CloudError('연결 요청 내용을 확인하세요.')
        action=parsed.path.removeprefix('/api/onedrive/')
        if action=='status' and handler.command=='GET':
            handler.reply(200,cloud.status(origin))
        elif action=='configure' and handler.command=='POST':
            import ipaddress
            if not origin.startswith('https:') and not ipaddress.ip_address(handler.client_address[0]).is_loopback:
                raise CloudError('비밀 값은 이 Mac에서 직접 설정하거나 HTTPS 접속으로 입력하세요.')
            cloud.configure(body.get('client_id'),body.get('secret'))
            handler.reply(200,cloud.status(origin))
        elif action=='connect' and handler.command=='POST':
            binding=secrets.token_urlsafe(32)
            url=cloud.begin(origin,binding,session_token)
            handler.session_cookie='media_cloud='+binding+'; HttpOnly; SameSite=Lax; Path=/api/onedrive/; Max-Age=600'+cookie_security
            handler.reply(200,{'url':url})
        elif action=='disconnect' and handler.command=='POST':
            cloud.disconnect();handler.reply(200,cloud.status(origin))
        elif action=='shared-archive' and handler.command=='POST':
            handler.reply(200,cloud.select_shared_archive(body.get('url')))
        elif action=='clear-shared-archive' and handler.command=='POST':
            cloud.clear_shared_archive()
            handler.reply(200,cloud.status(origin))
        elif action=='folders' and handler.command=='GET':
            handler.reply(200,{'items':[i for i in cloud.children(argument('id','root')) if 'folder' in i]})
        elif action=='folders' and handler.command=='POST':
            handler.reply(200,{'folders':cloud.select_folder(body.get('purpose'),body.get('id'))})
        elif action=='files' and handler.command=='GET':
            purpose=argument('purpose','source')
            if purpose not in ('source','source_video','archive', 'archive_wednesday','archive_friday_zoom','archive_friday_in_person','archive_sunday_ppt','archive_sunday_pdf'):
                raise CloudError('자료 종류를 확인하세요.')
            items=cloud.list_selected(purpose,argument('id') or None,argument('q'))
            if purpose=='source':
                from .original_roles import original_role
                items=[{**item,'source_role':original_role(item.get('name',''))}
                       if 'file' in item else item for item in items]
            handler.reply(200,{'items':items})
        elif action=='auto-connect' and handler.command=='POST':
            handler.reply(200,cloud.auto_connect())
        elif action=='import' and handler.command=='POST':
            handler.reply(201,cloud.import_song(body.get('id'),body.get('song_id')))
        elif action=='import-to-slot' and handler.command=='POST':
            handler.reply(201,cloud.import_for_service(body.get('id'),body.get('date'),
                                                        body.get('service'),body.get('slot')))
        elif action=='upload-source' and handler.command=='POST':
            handler.reply(201,cloud.upload_song(body.get('song_id'),body.get('digest')))
        elif action=='archive' and handler.command=='POST':
            handler.reply(201,cloud.archive(body.get('date'),body.get('service'),body.get('kind')))
        elif action=='download' and handler.command=='GET':
            if cloud.status(origin)['shared_archive']['enabled']:
                item=cloud.shared_archive_item(argument('id'))
            else:
                item=cloud.item(argument('id'))
                if not cloud.within(item,cloud.selected('archive')):
                    raise CloudError('완료본 폴더의 파일만 내려받을 수 있습니다.')
            handler.reply(200,cloud._download(item),'application/octet-stream')
        else:
            handler.reply(404,{'error':'지원하지 않는 OneDrive 요청입니다.'})
    except CloudError as error:
        handler.reply(400,{'error':str(error)})
    except Exception:
        # OAuth errors can contain credentials / codes. Never return raw errors.
        handler.reply(503,{'error':'OneDrive 작업을 완료하지 못했습니다. 연결 설정을 확인하거나 다시 시도하세요.'})
    return True
