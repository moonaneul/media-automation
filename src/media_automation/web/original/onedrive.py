"""Personal OneDrive integration. Credentials never leave the server.

One shared connection is used by the media team. File operations are restricted
by this application to the two explicitly chosen folders; Graph's delegated
Files.ReadWrite permission itself is broader than those folders.
"""
import json
import os
import re
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlsplit
import requests

AUTHORITY = 'https://login.microsoftonline.com/consumers'
GRAPH = 'https://graph.microsoft.com/v1.0'
SCOPES = ['Files.ReadWrite', 'User.Read']  # MSAL adds offline_access / OIDC scopes.
CLIENT_ID = '8831211f-ba82-43b8-b76e-98451efb0a6c'
CALLBACK = '/api/onedrive/callback'
MAX_FILE = 128 * 1024 * 1024
MAX_ARCHIVE_FILE = 512 * 1024 * 1024


class CloudError(ValueError):
    pass


def valid_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9!_.-]{1,200}', value):
        raise CloudError('OneDrive 항목을 확인하세요.')
    return quote(value, safe='')


def public_item(item):
    return {k: item[k] for k in ('id', 'name', 'size', 'webUrl', 'folder', 'file', 'parentReference', 'lastModifiedDateTime') if k in item}


class OneDrive:
    def __init__(self, store, connection_backend=None):
        self.store = store
        self.connection_backend = connection_backend
        self.folder = Path(store.path).with_suffix('.onedrive')
        self.lock = threading.RLock()
        self.pending = {}
        self.http = requests.Session()

    def _cipher(self):
        from cryptography.fernet import Fernet
        self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.folder, 0o700)
        key = self.folder / 'encryption.key'
        if not key.exists():
            try:
                fd = os.open(key, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(Fernet.generate_key())
            except FileExistsError:
                pass
        os.chmod(key, 0o600)
        return Fernet(key.read_bytes())

    def _read(self):
        if self.connection_backend is not None:
            return self.connection_backend.read()
        path = self.folder / 'connection.enc'
        if not path.exists():
            return {'client_id': CLIENT_ID}
        try:
            return json.loads(self._cipher().decrypt(path.read_bytes()))
        except Exception:
            raise CloudError('OneDrive 연결 정보를 읽지 못했습니다. 서버의 암호화 키를 확인하세요.') from None

    def _write(self, data):
        if self.connection_backend is not None:
            return self.connection_backend.write(data)
        encrypted = self._cipher().encrypt(json.dumps(data).encode())
        temporary = self.folder / ('connection.' + secrets.token_hex(8) + '.tmp')
        fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encrypted)
        temporary.replace(self.folder / 'connection.enc')

    def configure(self, client_id, secret):
        try:
            import uuid
            client_id = str(uuid.UUID(client_id))
        except (ValueError, TypeError, AttributeError):
            raise CloudError('애플리케이션(클라이언트) ID를 확인하세요.') from None
        if not isinstance(secret, str) or not 10 <= len(secret) <= 4096:
            raise CloudError('Microsoft에서 만든 클라이언트 비밀 값(Value)을 입력하세요.')
        with self.lock:
            data = self._read()
            if data.get('client_id') != client_id or data.get('secret') != secret:
                data = {'client_id': client_id, 'secret': secret}
                self.pending.clear()
            self._write(data)

    def status(self, origin):
        with self.lock:
            data = self._read()
            local_url = origin.replace('http://127.0.0.1:', 'http://localhost:') if origin.startswith('http://127.0.0.1:') else None
            return dict(configured=bool(data.get('secret')), client_id=data['client_id'],
                        redirect_uri=(local_url or origin) + CALLBACK, local_url=local_url,
                        connected=bool(data.get('account')),
                        account=data.get('account'), folders=data.get('folders', {}))

    def _app(self, data):
        import msal
        if not data.get('secret'):
            raise CloudError('Microsoft 앱의 반환 주소와 클라이언트 비밀을 먼저 설정하세요.')
        cache = msal.SerializableTokenCache()
        if data.get('cache'):
            cache.deserialize(data['cache'])
        app = msal.ConfidentialClientApplication(data['client_id'], client_credential=data['secret'],
                                                authority=AUTHORITY, token_cache=cache)
        return app, cache

    def begin(self, origin, browser_binding, session_token):
        with self.lock:
            if origin.startswith('http://127.0.0.1:'):
                raise CloudError('로컬 Microsoft 로그인은 localhost 주소에서 시작하세요.')
            if not origin.startswith(('https://', 'http://localhost:')):
                raise CloudError('OneDrive 로그인은 이 Mac의 localhost 또는 배포된 HTTPS 주소에서 시작하세요.')
            data = self._read()
            app, _ = self._app({k:v for k,v in data.items() if k != 'cache'})
            flow = app.initiate_auth_code_flow(SCOPES, redirect_uri=origin + CALLBACK, prompt='select_account')
            now = time.time()
            self.pending = {k: v for k, v in self.pending.items() if v['expires'] > now}
            if len(self.pending) >= 20:
                raise CloudError('연결 요청이 많습니다. 잠시 후 다시 시도하세요.')
            self.pending[flow['state']] = dict(flow=flow, binding=browser_binding, session=session_token, expires=now+600)
            return flow['auth_uri']

    def finish(self, query, browser_binding, session_valid):
        with self.lock:
            attempt = self.pending.pop(query.get('state', ''), None)
            if (not attempt or attempt['expires'] < time.time() or not browser_binding
                    or not secrets.compare_digest(attempt['binding'], browser_binding)
                    or not session_valid(attempt['session'])):
                raise CloudError('로그인 요청이 만료됐거나 브라우저가 다릅니다. 연결 버튼으로 다시 시작하세요.')
            data = self._read()
            app, cache = self._app({k:v for k,v in data.items() if k != 'cache'})
            result = app.acquire_token_by_auth_code_flow(attempt['flow'], query)
            if not result.get('access_token'):
                raise CloudError('Microsoft 로그인이 완료되지 않았습니다. 반환 주소·비밀 만료일·권한 승인을 확인하세요.')
            accounts = app.get_accounts()
            if not accounts:
                raise CloudError('로그인한 계정을 확인하지 못했습니다.')
            account = accounts[0]
            # Switching accounts must never retain folder IDs from another drive.
            if data.get('account', {}).get('home_account_id') != account['home_account_id']:
                data.pop('folders', None)
            data.update(account={'home_account_id': account['home_account_id'], 'username': account.get('username', '')},
                        cache=cache.serialize())
            self._write(data)

    def disconnect(self):
        with self.lock:
            data = self._read()
            for key in ('cache', 'account', 'folders'):
                data.pop(key, None)
            self.pending.clear()
            self._write(data)

    def _token(self):
        with self.lock:
            data = self._read()
            if not data.get('account'):
                raise CloudError('설정에서 OneDrive에 연결하세요.')
            app, cache = self._app(data)
            accounts = [account for account in app.get_accounts()
                        if account.get('home_account_id') == data['account']['home_account_id']]
            result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
            if cache.has_state_changed:
                data['cache'] = cache.serialize()
                self._write(data)
            if not result or not result.get('access_token'):
                raise CloudError('OneDrive 연결을 갱신해야 합니다. 설정에서 다시 로그인하세요.')
            return result['access_token']

    def graph(self, path, method='GET', body=None, content=None):
        url = GRAPH + path if path.startswith('/') else path
        parts = urlsplit(url)
        if parts.scheme != 'https' or parts.netloc != 'graph.microsoft.com' or not (parts.path == '/v1.0/me/drive' or parts.path.startswith('/v1.0/me/drive/')):
            raise CloudError('허용되지 않은 OneDrive 요청입니다.')
        headers = {'Authorization': 'Bearer ' + self._token()}
        if content is not None:
            headers['Content-Type'] = 'application/octet-stream'
        try:
            response = self.http.request(method, url, headers=headers, json=body, data=content,
                                         timeout=(10,120), allow_redirects=False)
            if not 200 <= response.status_code < 300:
                messages = {
                    401: 'OneDrive 로그인이 만료됐습니다. 설정에서 다시 로그인하세요.',
                    403: 'OneDrive 파일·폴더 접근 권한을 확인하세요.',
                    404: 'OneDrive 파일·폴더를 찾지 못했습니다. 이동·삭제 여부를 확인하고 다시 선택하세요.',
                    429: 'OneDrive 요청이 많습니다. 잠시 후 다시 시도하세요.',
                    507: 'OneDrive 저장 공간이 부족합니다. 여유 공간을 확보하고 다시 저장하세요.',
                }
                if response.status_code in messages:
                    raise CloudError(messages[response.status_code])
                if response.status_code >= 500:
                    raise CloudError('OneDrive에 일시적인 장애가 있습니다. 잠시 후 다시 시도하세요.')
                raise CloudError('OneDrive 요청에 실패했습니다. 연결 상태·폴더 권한·저장 공간을 확인하세요.')
            return response.json()
        except requests.RequestException:
            raise CloudError('OneDrive에 연결하지 못했습니다. 잠시 후 다시 시도하세요.') from None

    def item(self, identifier):
        return self.graph('/me/drive/root' if identifier == 'root' else '/me/drive/items/' + valid_id(identifier))

    def children(self, identifier='root', query=''):
        base = '/me/drive/root' if identifier == 'root' else '/me/drive/items/' + valid_id(identifier)
        if query:
            if len(query) > 100:
                raise CloudError('검색어는 100자 이내로 입력하세요.')
            path = base + "/search(q='" + quote(query.replace("'", "''"), safe='') + "')?$top=200"
        else:
            path = base + '/children?$top=200'
        items = []
        for _ in range(20):
            result = self.graph(path)
            items.extend(public_item(v) for v in result.get('value', []) if not v.get('remoteItem'))
            path = result.get('@odata.nextLink')
            if not path:
                return items
        raise CloudError('검색 결과가 너무 많습니다. 하위 폴더나 더 구체적인 검색어를 사용하세요.')

    def select_folder(self, purpose, identifier):
        if purpose not in ('source', 'archive') or identifier == 'root':
            raise CloudError('원본·완료본용 하위 폴더를 선택하세요.')
        item = self.item(identifier)
        if 'folder' not in item or item.get('remoteItem'):
            raise CloudError('본인 OneDrive의 폴더를 선택하세요.')
        with self.lock:
            data = self._read()
            folders = data.setdefault('folders', {})
            other = folders.get('archive' if purpose == 'source' else 'source')
            if other and (self.within(item,other) or self.within(self.item(other['id']),item)):
                raise CloudError('원본과 완료본은 서로 포함되지 않는 별도 폴더를 선택하세요.')
            folders[purpose] = public_item(item)
            self._write(data)
        return folders

    def selected(self, purpose):
        with self.lock:
            folder = self._read().get('folders', {}).get(purpose)
        if not folder:
            raise CloudError('설정에서 ' + ('찬양 원본' if purpose == 'source' else '완료본') + ' 폴더를 선택하세요.')
        return folder

    def upload_file(self, folder_id, name, content):
        path='/me/drive/items/'+valid_id(folder_id)+':/'+quote(name,safe='')
        if len(content)<4*1024*1024:
            return self.graph(path+':/content',method='PUT',content=content)
        existing=[item for item in self.children(folder_id) if item.get('name')==name]
        if existing:
            if len(existing)==1 and 'file' in existing[0] and existing[0].get('size')==len(content):return existing[0]
            if len(existing)!=1 or 'file' not in existing[0] or existing[0].get('size')!=0:
                raise CloudError('동일 이름의 기존 파일을 확인하세요.')
            session_path='/me/drive/items/'+valid_id(existing[0]['id'])+'/createUploadSession'
        else:
            session_path=path+':/createUploadSession'
        session=self.graph(session_path,method='POST',
                           body={})
        url=session.get('uploadUrl','');parts=urlsplit(url)
        if parts.scheme!='https' or parts.username or parts.password or parts.port not in (None,443) or not any(
                parts.hostname==domain or (parts.hostname or '').endswith('.'+domain)
                for domain in ('1drv.com','onedrive.com','sharepoint.com','microsoftpersonalcontent.com')):
            raise CloudError('Microsoft 업로드 주소를 확인하지 못했습니다.')
        chunk_size=5*1024*1024
        for start in range(0,len(content),chunk_size):
            chunk=content[start:start+chunk_size]
            try:
                response=self.http.put(url,data=chunk,headers={'Content-Range':f'bytes {start}-{start+len(chunk)-1}/{len(content)}'},
                                       timeout=(10,120),allow_redirects=False)
            except requests.RequestException:
                raise CloudError('파일 전송이 중단됐습니다. 다시 저장해 주세요.') from None
            if response.status_code in (200,201):
                item=response.json()
                if start+len(chunk)!=len(content) or item.get('size')!=len(content):
                    raise CloudError('업로드 완료 파일의 크기를 확인하세요.')
                return item
            if response.status_code!=202:
                raise CloudError('OneDrive 분할 업로드에 실패했습니다. 다시 저장해 주세요.')
        raise CloudError('OneDrive 업로드 완료를 확인하지 못했습니다.')

    def upload_song(self, song_id, digest):
        folder = self.selected('source')
        with self.store.connect() as db:
            row = db.execute('SELECT filename FROM song_assets WHERE song_id=? AND digest=?',(song_id,digest)).fetchone()
        if not row or not re.fullmatch('[a-f0-9]{64}',digest or ''):
            raise CloudError('등록된 원본을 확인하세요.')
        path = Path(self.store.path).with_suffix('.files')/digest
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_FILE:
            raise CloudError('원본 파일을 찾지 못했거나 128MB를 초과합니다.')
        original = Path(row[0])
        # Content hash separates versions and deduplicates repeat uploads.
        name = original.stem[:100]+'_'+digest+original.suffix
        item = self.upload_file(folder['id'],name,path.read_bytes())
        return {'item':public_item(item)}

    def within(self, item, folder):
        """Check ancestry on the server, never trust a browser-supplied path."""
        seen = set()
        for _ in range(40):
            if item.get('id') == folder['id']:
                return True
            parent = item.get('parentReference', {})
            parent_id = parent.get('id')
            if not parent_id or parent_id in seen or parent.get('driveId') != folder.get('parentReference', {}).get('driveId'):
                return False
            seen.add(parent_id)
            item = self.item(parent_id)
        return False

    def list_selected(self, purpose, identifier=None, query=''):
        folder = self.selected(purpose)
        if identifier and identifier != folder['id'] and not self.within(self.item(identifier), folder):
            raise CloudError('지정한 자료 폴더 안에서만 조회할 수 있습니다.')
        return self.children(identifier or folder['id'], query)

    def _download(self, item):
        if not 0 < item.get('size', 0) <= MAX_FILE or 'file' not in item:
            raise CloudError('파일은 128MB 이하만 불러올 수 있습니다.')
        # Graph supplies an expiring preauthenticated URL. Never send the Graph
        # access token to this file host or expose the URL to the browser.
        url = item.get('@microsoft.graph.downloadUrl', '')
        def allowed(value):
            p = urlsplit(value)
            return p.scheme == 'https' and not p.username and not p.password and p.port in (None,443) and any(
                p.hostname == domain or (p.hostname or '').endswith('.'+domain)
                for domain in ('1drv.com','onedrive.com','onedrive.live.com','storage.live.com','sharepoint.com','microsoftpersonalcontent.com'))
        for _ in range(5):
            if not allowed(url):
                raise CloudError('Microsoft 파일 다운로드 주소를 확인하지 못했습니다.')
            try:
                with self.http.get(url, timeout=(10,120), stream=True, allow_redirects=False) as response:
                    if response.status_code in (301,302,303,307,308):
                        url = response.headers.get('Location','')
                        continue
                    if response.status_code != 200:
                        raise CloudError('OneDrive 파일을 내려받지 못했습니다.')
                    chunks=[];size=0
                    for chunk in response.iter_content(1024*1024):
                        size += len(chunk)
                        if size > MAX_FILE:
                            raise CloudError('파일은 128MB 이하만 불러올 수 있습니다.')
                        chunks.append(chunk)
                    if size != item['size']:
                        raise CloudError('다운로드한 파일 크기가 원본과 다릅니다. 다시 시도하세요.')
                    return b''.join(chunks)
            except requests.RequestException:
                raise CloudError('원본 파일 다운로드 중 연결이 끊겼습니다. 다시 시도하세요.') from None
        raise CloudError('다운로드 주소가 너무 많이 변경됐습니다.')

    def import_song(self, identifier, song_id):
        from .original_roles import song_candidate
        folder = self.selected('source')
        if song_id not in {s['id'] for s in self.store.songs()}:
            raise CloudError('연결할 등록 곡을 선택하세요.')
        item = self.item(identifier)
        if not self.within(item, folder):
            raise CloudError('찬양 원본 폴더 안의 파일만 불러올 수 있습니다.')
        if not song_candidate(item.get('name','')):
            raise CloudError('찬양 원본이 아닙니다. 주보·템플릿·기도 자료는 별도 자료로 관리하세요.')
        content = self._download(item)
        result = self.store.attach_song_asset(song_id, item['name'], content)
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cloud_song_sources (song_id TEXT,digest TEXT,drive_item TEXT,PRIMARY KEY(song_id,digest))')
            db.execute('INSERT OR REPLACE INTO cloud_song_sources VALUES (?,?,?)',(song_id,result['digest'],item['id']))
        return result

    def import_for_service(self, identifier, day, service, slot):
        """Import ONE explicitly selected OneDrive source into ONE worship slot.

        No broad auto-linking and no change to the original OneDrive file.
        This preserves the existing field value; the user must rebuild and
        inspect the PPT before the score can be called inserted.
        """
        from .original_roles import song_candidate
        from .generation import compatible_original

        self.store.validate(day, service)
        if not isinstance(slot, str) or len(slot) > 200:
            raise CloudError('예배 찬양 항목을 확인하세요.')
        is_song = any(word in slot for word in ('찬양', '찬송', '특송'))
        is_background = slot.startswith('배경음악 ')
        if not is_song and not is_background:
            raise CloudError('찬양·찬송·특송 원본만 이 기능으로 연결할 수 있습니다.')
        current = self.store.get(day, service)['data']
        field = current.get('fields', {}).get(slot)
        if not is_background and (not isinstance(field, dict) or field.get('state') != 'VALUE'
                                  or not field.get('value', '').strip()):
            raise CloudError('이번 주 예배에 해당 찬양의 곡명을 먼저 입력하세요.')
        mode = current.get('fridayMode', 'zoom')
        if is_background and (service != 'friday' or mode != 'zoom'):
            raise CloudError('배경음악은 금요 Zoom에서만 선택할 수 있습니다.')
        folder = self.selected('source')
        item = self.item(identifier)
        if not self.within(item, folder):
            raise CloudError('선택한 OneDrive 찬양 원본 폴더의 파일만 가져올 수 있습니다.')
        filename = item.get('name', '')
        if (not compatible_original(filename, service, mode, slot)
                or not isinstance(filename, str) or not filename):
            raise CloudError('현재 예배 방식과 맞지 않는 원본입니다. 대면은 악보 PPT, Zoom 찬양은 MP4입니다.')
        if not is_background and not song_candidate(filename):
            raise CloudError('주보·표지·템플릿 등 찬양 이외의 원본은 연결할 수 없습니다.')
        content = self._download(item)
        # WorkStore stores the bytes under SHA-256 and updates only this one
        # attachment; no song-catalog review or copyright permission is inferred.
        result = self.store.attach(day, service, slot, filename, content)
        if result['conversion_status'] == 'failed':
            return dict(result, source='onedrive', imported=True, ready_for_ppt=False)
        return dict(result, source='onedrive', imported=True, ready_for_ppt=True)

    @staticmethod
    def filename_metadata(filename):
        import unicodedata
        stem=unicodedata.normalize('NFKC',Path(filename).stem)
        stem=re.sub(r'_[a-f0-9]{64}$','',stem)
        edition='new' if '새찬송가' in stem else 'old' if '구찬송가' in stem else None
        numbered=re.search(r'(?:^|찬송가\s*)(\d{1,3})\s*장',stem)
        if numbered:
            if not edition:return None
            title=stem[numbered.end():].strip(' _.-')
            title=re.split(r'[_]?(?:새찬송가|구찬송가|악보|PPT)',title,flags=re.I)[0].strip(' _.-')
            if not title:return None
            return {'title':title,'edition':edition,'number':int(numbered[1]),'aliases':[]}
        if re.match(r'^\d',stem):return None
        title=stem.split('_')[0].strip()
        if not title or len(title)>200:return None
        return {'title':title,'edition':None,'number':None,'aliases':[]}

    @staticmethod
    def filename_song(filename, songs):
        import unicodedata
        def normalized(value):
            return ''.join(c for c in unicodedata.normalize('NFKC',value).lower() if c.isalnum())
        stem = unicodedata.normalize('NFKC',Path(filename).stem)
        stem = re.sub(r'_[a-f0-9]{64}$','',stem)
        metadata=OneDrive.filename_metadata(filename)
        if metadata:
            candidates=[song for song in songs if (song.get('edition')==metadata['edition'] and song.get('number')==metadata['number']
                        and normalized(song['title'])==normalized(metadata['title'])) or
                        (not metadata['edition'] and normalized(metadata['title']) in [normalized(v) for v in [song['title'],*song.get('aliases',[])]])]
            if len(candidates)==1:return candidates[0]
        match = re.fullmatch(r'\s*(새찬송가|구찬송가|찬송가)?\s*(\d{1,3})(?:\s*장|[ _.-]+)(.*)',stem)
        if match:
            label,number,title = match.groups()
            edition = {'새찬송가':'new','구찬송가':'old'}.get(label)
            candidates = [song for song in songs if song.get('number') == int(number)
                          and (not edition or song.get('edition') == edition)]
            if title.strip():
                candidates = [song for song in candidates if normalized(title) in
                              [normalized(v) for v in [song['title'],*song.get('aliases',[])]]]
            # A bare number never decides old/new hymnal on its own.
            if not edition and not title.strip():
                return None
        else:
            candidates = [song for song in songs if normalized(stem) in
                          [normalized(v) for v in [song['title'],*song.get('aliases',[])]]]
        return candidates[0] if len(candidates)==1 else None

    def auto_connect(self):
        from .original_roles import original_role, song_candidate, can_auto_register_hymn
        folder = self.selected('source')
        pending = [folder['id']]; seen=set();files=[]
        while pending:
            identifier=pending.pop()
            if identifier in seen:continue
            seen.add(identifier)
            if len(seen)>200:raise CloudError('원본 폴더가 너무 많습니다. 폴더 구성을 확인하세요.')
            for item in self.children(identifier):
                if 'folder' in item:pending.append(item['id'])
                elif 'file' in item and song_candidate(item.get('name','')):
                    files.append(item)
            if len(files)>4000:raise CloudError('원본이 너무 많습니다. 검색 범위를 줄여 주세요.')
        songs=self.store.songs(); groups={}; undecided=[]
        for item in files:
            song=self.filename_song(item['name'],songs)
            if not song:
                metadata=self.filename_metadata(item['name'])
                if can_auto_register_hymn(metadata, item['name']):
                    # Only named hymn scores create songs; other files require selection.
                    conflict=any((metadata['edition'] and v.get('edition')==metadata['edition'] and v.get('number')==metadata['number']) or v['title']==metadata['title'] for v in songs)
                    if not conflict:
                        song=self.store.register_song(metadata);songs.append(song)
            if song:groups.setdefault(song['id'],[]).append(item)
            else:undecided.append({'name':item['name'],'reason':'곡명·찬송가 종류 확인 필요'})
        result={'linked':0,'unchanged':0,'pending':0,'choices':undecided,'errors':[]}
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cloud_auto_sources (item_id TEXT PRIMARY KEY,song_id TEXT,stamp TEXT,digest TEXT)')
        for song_id,items in groups.items():
            if len(items)!=1:
                result['choices'].extend({'name':v['name'],'reason':'같은 곡의 원본이 여러 개 · 직접 선택'} for v in items)
                continue
            item=items[0];stamp=str(item.get('lastModifiedDateTime',''))+':'+str(item.get('size',''))
            with self.store.connect() as db:
                prior=db.execute('SELECT stamp,digest FROM cloud_auto_sources WHERE item_id=? AND song_id=?',(item['id'],song_id)).fetchone()
                registered=prior and db.execute('SELECT 1 FROM song_assets WHERE song_id=? AND digest=?',(song_id,prior[1])).fetchone()
            if prior and not registered and prior[0]==stamp:
                result['choices'].append({'name':item['name'],'reason':'삭제·교체된 원본 · 필요하면 직접 연결'})
                continue
            if prior and registered and prior[0]==stamp:
                result['unchanged']+=1;continue
            if result['linked']>=20:
                result['pending']+=1;continue
            try:
                imported=self.import_song(item['id'],song_id)
                with self.store.connect() as db:
                    db.execute('INSERT OR REPLACE INTO cloud_auto_sources VALUES (?,?,?,?)',(item['id'],song_id,stamp,imported['digest']))
                result['linked']+=1
            except CloudError as error:result['errors'].append({'name':item['name'],'reason':str(error)})
        return result

    def archive_destination(self, service, kind):
        """Reuse or create the agreed subfolders under the chosen archive root."""
        names = {'wednesday':['수요 예배'], 'friday':['금요 기도회'],
                 'sunday':['주일 예배', '주보' if kind == 'pdf' else '예배 PPT']}[service]
        folder = self.selected('archive')
        for name in names:
            matches = [v for v in self.children(folder['id']) if v.get('name') == name]
            if matches:
                child = matches[0]
                if 'folder' not in child:
                    raise CloudError(name + ' 이름의 파일이 있습니다. 폴더 이름을 확인하세요.')
            else:
                child = self.graph('/me/drive/items/'+valid_id(folder['id'])+'/children', method='POST',
                                   body={'name':name, 'folder':{}, '@microsoft.graph.conflictBehavior':'fail'})
            if 'folder' not in child or not child.get('id'):
                raise CloudError('완료본 하위 폴더를 확인하지 못했습니다.')
            folder = child
        return folder

    def archive(self, day, service, kind):
        self.store.validate(day,service)
        if kind not in ('ppt','pdf'):
            raise CloudError('파일 종류를 확인하세요.')
        folder = self.selected('archive')
        current = self.store.get(day,service)
        output = current['data'].get('outputs',{}).get(kind,{})
        identifier = output.get('fileId','')
        if not output.get('complete') or output.get('changed') or not re.fullmatch('[a-f0-9]{32}',identifier):
            raise CloudError('최신 결과를 검수하고 제작 완료 표시한 후 보관하세요.')
        extension = 'pdf' if kind == 'pdf' else 'pptx'
        path = Path(self.store.path).with_suffix('.generated')/(identifier+'.'+extension)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_ARCHIVE_FILE:
            raise CloudError('완료 파일을 찾지 못했거나 512MB를 초과합니다.')
        folder = self.archive_destination(service, kind)
        name = f'{day}_{service}_{kind}_{identifier}.{extension}'
        item = self.upload_file(folder['id'],name,path.read_bytes())
        latest = self.store.get(day,service)
        latest_output = latest['data'].get('outputs',{}).get(kind,{})
        if (latest_output.get('fileId') == identifier and latest['revision'] == current['revision']
                and latest_output.get('complete') and not latest_output.get('changed')):
            latest_output.update(archiveStatus='uploaded',cloudItem=public_item(item))
            saved = self.store.save(day,service,latest['revision'],latest['data'])
        else:
            saved = latest
        with self.store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS cloud_archives (file_id TEXT PRIMARY KEY,day TEXT,service TEXT,kind TEXT,item TEXT)')
            db.execute('INSERT OR REPLACE INTO cloud_archives VALUES (?,?,?,?,?)',(identifier,day,service,kind,json.dumps(public_item(item))))
        return dict(item=public_item(item),work=saved)
