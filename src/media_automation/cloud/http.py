"""Hosted adapter for the existing church UI, without a local database."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time
import hashlib
from urllib.parse import parse_qs
from uuid import uuid4

from .artifacts import download_verified, upload_verified
from .job_api import JobClient
from .supabase_auth import AccessDenied
from .supabase_work_store import WorkStoreUnavailable, validate_work
from ..web.original.work_store import RevisionConflict, WorkStore
from ..web.original.production_order import build_order
from ..web.original.generation import compatible_original, render_configuration
from ..web.streaming_download import send_download


class Hosted:
    script = Path(__file__).with_name('ui') / 'cloud-runtime.js'

    def __init__(self, auth, sessions, cloud, backend, dispatcher):
        self.auth, self.sessions, self.cloud = auth, sessions, cloud
        self.backend, self.dispatcher = backend, dispatcher

    def client(self, token):
        return JobClient(self.auth.url, self.auth.key, token)

    @staticmethod
    def body(handler, limit=1024 * 1024):
        size = int(handler.headers.get('Content-Length', '-1'))
        if handler.headers.get('Content-Type') != 'application/json' or not 0 < size <= limit:
            raise ValueError('입력 형식·크기를 확인하세요.')
        body = json.loads(handler.rfile.read(size))
        if not isinstance(body, dict):
            raise ValueError('입력 형식을 확인하세요.')
        return body

    @staticmethod
    def catalog(client, day='1900-01-01', service='wednesday'):
        current = client.get(day, service)
        return client.snapshot(day, service, current['revision'])

    @staticmethod
    def songs(snapshot):
        tables = snapshot['tables']
        reviews = {(r['song_id'], r['digest']): r['payload'] for r in tables['reviews']}
        songs = [deepcopy(r['payload']) for r in tables['songs']]
        for song in songs:
            song['assets'] = []
            for row in tables['song_assets']:
                if row['song_id'] != song['id']:
                    continue
                review = reviews.get((song['id'], row['digest']), {
                    'technical': False, 'church': False, 'permission': 'unknown', 'note': ''})
                song['assets'].append({'digest': row['digest'], 'filename': row['filename'],
                    'review': review, 'review_status': 'unreviewed',
                    'eligible': review['technical'] and review['church'] and review['permission'] == 'allowed',
                    'archive_status': 'uploaded'})
        return songs

    @staticmethod
    def edit(client, snapshot, operation, body):
        result = client._request('POST', '/rest/v1/rpc/media_edit_catalog', json={
            'p_revision': snapshot['catalog_revision'], 'p_operation': operation, 'p_body': body})
        if not isinstance(result, dict) or result.get('saved') is not True:
            raise RevisionConflict({'revision': result.get('revision', 0), 'data': {}})
        return result

    def handle(self, handler, parsed, token, member):
        client = self.client(token)
        query = parse_qs(parsed.query)
        path, method = parsed.path, handler.command
        reply = handler.reply
        try:
            if path == '/api/upload-start' and method == 'POST':
                return reply(200, self.upload_start(client, member, self.body(handler, 16384)))
            if path == '/api/upload-finish' and method == 'POST':
                return reply(201, self.upload_finish(client, member, self.body(handler, 32768)))
            if path == '/api/work':
                day, service = query['date'][0], query['service'][0]
                if method == 'GET':
                    current = client.get(day, service)
                    current = self.with_results(client, day, service, current)
                    return reply(200, current)
                data = self.body(handler)
                return reply(200, client.save(day, service, data['revision'], data['data']))
            if path == '/api/production-order' and method == 'POST':
                body = self.body(handler)
                current = client.get(body['date'], body['service'])
                if current['revision'] != body['revision']:
                    raise RevisionConflict(current)
                return reply(200, {'order': build_order(body['groups'], current['data'].get('fields', {}), body['service']),
                                   'revision': current['revision'], 'file_generated': False})
            if path == '/api/build' and method == 'POST':
                body = self.body(handler)
                result = client.start(body['date'], body['service'], body['revision'], body['output'],
                                      body['groups'], body['request_key'])
                if result.get('busy'):
                    return reply(409, {'error': '다른 제작이 진행 중입니다. 작업 상태를 확인하세요.'})
                if result['status'] == 'queued':
                    try:
                        self.dispatcher.start(result['id'])
                    except WorkStoreUnavailable:
                        result['dispatch_unknown'] = True
                return reply(202, result)
            if path == '/api/jobs':
                if method == 'POST':
                    return reply(200, client.cancel(self.body(handler)['id']))
                if 'id' not in query:
                    jobs=client.list(query['date'][0],query['service'][0])
                    return reply(200, {'jobs': [{k:r.get(k) for k in ('id','status','result','day','service','revision','output','deadline','created_at')}
                        for r in jobs]})
                result = client.status(query['id'][0])
                # Expose the generated result only after finish has committed.
                if result['status'] != 'succeeded':
                    result['result'] = {'error': (result.get('result') or {}).get('error')} if result['status'] == 'failed' else None
                return reply(200, result)
            if path in ('/api/generated', '/api/generated-report', '/api/ppt-preview', '/api/pdf-preview'):
                job = client.artifact_job(query['id'][0])
                result = job['result']
                if path == '/api/generated':
                    expected = 'pdf' if job['output'] == 'pdf' else 'pptx'
                    if query.get('format', ['pptx'])[0] != expected:
                        raise ValueError('파일 형식을 확인하세요.')
                    record = result['artifact']
                else:
                    record = result['report'] if path == '/api/generated-report' else result['preview']
                with tempfile.TemporaryDirectory(prefix='media-hosted-download-') as folder:
                    target = Path(folder) / record['filename']
                    download_verified(self.cloud, record, target)
                    if path == '/api/generated':
                        return send_download(handler, target)
                    if path == '/api/generated-report':
                        return reply(200, json.loads(target.read_text()))
                    import pymupdf
                    with pymupdf.open(target) as doc:
                        page = int(query.get('page', ['1'])[0])
                        if not 1 <= page <= len(doc):
                            raise ValueError('페이지 번호를 확인하세요.')
                        scale = 1200 / max(doc[page - 1].rect.width, doc[page - 1].rect.height)
                        return reply(200, doc[page - 1].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png'), 'image/png')
            if path == '/api/songs':
                snapshot = self.catalog(client)
                if method == 'GET':
                    return reply(200, {'songs': self.songs(snapshot)})
                body = self.body(handler, 16384)
                with tempfile.TemporaryDirectory() as folder:
                    song = WorkStore(Path(folder) / 'validation.db').register_song(body)
                self.edit(client, snapshot, 'song', {'song': song})
                return reply(201, song)
            if path == '/api/attachments' and method == 'GET':
                snapshot = self.catalog(client, query['date'][0], query['service'][0])
                return reply(200, {'attachments': [{**row, 'archive_status': 'uploaded'}
                    for row in snapshot['tables']['attachments']]})
            if path in ('/api/attachments', '/api/song-assets') and method == 'POST':
                # Cloud Run HTTP/1 requests are bounded. Large files use the direct upload API.
                size = int(handler.headers.get('Content-Length', '-1'))
                if handler.headers.get('Content-Type') != 'application/octet-stream' or not 0 < size <= 24 * 1024 * 1024:
                    return reply(413, {'error': '큰 파일은 분할 업로드로 등록하세요.'})
                content = handler.rfile.read(size)
                if len(content) != size:
                    raise ValueError('파일 전송이 끝나지 않았습니다.')
                return reply(201, self.upload(client, path, query, content))
            if path == '/api/asset-review' and method == 'POST':
                body = self.body(handler, 16384)
                snapshot = self.catalog(client)
                with tempfile.TemporaryDirectory() as folder:
                    store = WorkStore(Path(folder) / 'validation.db')
                    with store.connect() as db:
                        for row in snapshot['tables']['song_assets']:
                            db.execute('insert into song_assets values(?,?,?)', (row['song_id'], row['digest'], row['filename']))
                    review = store.review_asset(body['song_id'], body['digest'], body['review'])
                self.edit(client, snapshot, 'review', {**body, 'review': review})
                return reply(200, review)
            if path == '/api/remove-original' and method == 'POST':
                body = self.body(handler, 16384)
                if not body.get('song_id'):
                    validate_work(body['date'], body['service'])
                self.edit(client, self.catalog(client), 'remove', body)
                return reply(200, {'removed': True})
            if path == '/api/bulletin-settings':
                snapshot = self.catalog(client)
                rows = snapshot['tables']['settings']
                if len(rows) != 1:
                    raise WorkStoreUnavailable('확정 주보 설정을 찾지 못했습니다.')
                current = {'revision': rows[0]['revision'], 'data': rows[0]['payload']}
                if method == 'GET':
                    return reply(200, current)
                body = self.body(handler, 9 * 1024 * 1024)
                edited = body['data']
                for group in ('annual', 'church', 'meeting_times'):
                    if set(edited[group]) != set(current['data'][group]):
                        raise ValueError('설정 항목을 확인하세요.')
                    for key, value in edited[group].items():
                        if isinstance(current['data'][group][key], list):
                            if not isinstance(value, list) or len(value) > 30 or any(not isinstance(v, str) or len(v) > 2000 for v in value):
                                raise ValueError('설정 내용을 확인하세요.')
                        elif not isinstance(value, str) or len(value) > 5000:
                            raise ValueError('설정 내용을 확인하세요.')
                if type(edited.get('reference_year')) is not int or not 2000 <= edited['reference_year'] <= 2100:
                    raise ValueError('표어 적용 연도를 확인하세요.')
                if 'cover_photo' in edited:
                    from ..bulletin.cover_photo import photo_bytes
                    photo_bytes(edited['cover_photo'])
                edited['status'] = 'confirmed'
                self.edit(client, snapshot, 'settings', body)
                return reply(200, {'revision': body['revision'] + 1, 'data': edited})
            if path == '/api/notice-file' and method == 'POST':
                from ..web.original.notice_files import extract_notice
                size = int(handler.headers.get('Content-Length', '-1'))
                if handler.headers.get('Content-Type') != 'application/octet-stream' or not 0 < size <= 8 * 1024 * 1024:
                    raise ValueError('안내 파일은 8MB 이하로 첨부하세요.')
                return reply(200, extract_notice(query['filename'][0], handler.rfile.read(size)))
            if path in ('/api/original', '/api/asset-preview'):
                snapshot = self.catalog(client)
                record = next((row for row in snapshot['tables']['files'] if row['digest'] == query['digest'][0]), None)
                if record is None:
                    return reply(404, {'error': '등록된 원본을 찾지 못했습니다.'})
                with tempfile.TemporaryDirectory(prefix='media-original-preview-') as folder:
                    target = Path(folder) / record['filename']
                    download_verified(self.cloud, record, target, 'source')
                    if path == '/api/original':
                        return send_download(handler, target)
                    from ..web.original.ppt_conversion import convert_original
                    from ..web.pptx_preview import convert_pptx
                    if target.suffix.lower() == '.ppt':
                        target = convert_original(target)
                    pdf = Path(folder) / 'preview.pdf'
                    convert_pptx(target, pdf)
                    import pymupdf
                    with pymupdf.open(pdf) as doc:
                        if query.get('info') == ['1']:
                            return reply(200, {'page_count': len(doc)})
                        if 'page' not in query:
                            return send_download(handler, pdf)
                        page = int(query['page'][0])
                        if not 1 <= page <= len(doc):
                            raise ValueError('페이지 번호를 확인하세요.')
                        scale = 1200 / max(doc[page - 1].rect.width, doc[page - 1].rect.height)
                        return reply(200, doc[page - 1].get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes('png'), 'image/png')
            if path in ('/api/complete', '/api/complete-bulletin') and method == 'POST':
                return self.complete(handler, client)
            if path.startswith('/api/onedrive/'):
                return self.onedrive(handler, client, parsed)
            return reply(404, {'error': '없는 경로입니다.'})
        except RevisionConflict as exc:
            return reply(409, {'error': str(exc), 'current': exc.current})
        except AccessDenied:
            return reply(401, {'error': '로그인·팀 권한을 다시 확인하세요.'})
        except (ValueError, KeyError, TypeError, StopIteration):
            return reply(400, {'error': '입력·자료·저장 버전을 확인하세요.'})
        except Exception:
            return reply(503, {'error': '처리 결과를 확인하지 못했습니다. 다시 불러와 확인하세요.'})

    def upload(self, client, path, query, content):
        filename = query['filename'][0]
        with tempfile.TemporaryDirectory(prefix='media-cloud-source-') as folder:
            store = WorkStore(Path(folder) / 'upload.db')
            digest, _, target = store._store_file(filename, content)
            if path == '/api/attachments':
                day, service, slot = query['date'][0], query['service'][0], query['slot'][0]
                snapshot = self.catalog(client, day, service)
                mode = snapshot['work']['data'].get('fridayMode', 'zoom')
                if not compatible_original(filename, service, mode, slot):
                    raise ValueError('현재 예배 방식과 맞는 원본을 선택하세요.')
                operation, body = 'attachment', {'day': day, 'service': service, 'slot': slot}
            else:
                snapshot = self.catalog(client)
                operation, body = 'song_asset', {'replace_digest': query.get('replace_digest', [None])[0]}
            body.update(song_id=query.get('song_id', [None])[0], filename=filename, digest=digest)
            if body['song_id'] and not any(r['id'] == body['song_id'] for r in snapshot['tables']['songs']):
                raise ValueError('등록된 곡을 확인하세요.')
            existing = next((r for r in snapshot['tables']['files'] if r['digest'] == digest), None)
            if existing is None:
                record = upload_verified(self.cloud, target, self.cloud.selected('source'),
                    'original-' + uuid4().hex + '-' + filename, purpose='source')
                record['filename'] = filename
                self.backend.call('media_register_file', {'p_record': record})
            self.edit(client, snapshot, operation, body)
            return {**body, 'archive_status': 'uploaded', 'duplicate': existing is not None}

    def complete(self, handler, client):
        body = self.body(handler, 8192)
        if body.get('reviewed') is not True:
            raise ValueError('화면 검수를 확인하세요.')
        job = client.artifact_job(body['file_id'])
        if job['day'] != body['date'] or job['service'] != body['service']:
            raise ValueError('예배 날짜·종류를 확인하세요.')
        snapshot = self.catalog(client, body['date'], body['service'])
        current = self.with_results(client, body['date'], body['service'], snapshot['work'])
        if current['revision'] != body['revision']:
            raise RevisionConflict(current)
        with tempfile.TemporaryDirectory() as folder:
            report = job['result']['report']
            path = download_verified(self.cloud, report, Path(folder) / 'report.json')
            report = json.loads(path.read_text())
        if report['unresolved'] or report['fields'] != current['data']['fields']:
            raise ValueError('누락과 변경된 입력을 확인하세요.')
        if report.get('catalog_revision') != snapshot['catalog_revision']:
            raise ValueError('자료·설정이 변경됐습니다. 다시 제작하세요.')
        if job['output'] == 'ppt' and report.get('render_configuration') != render_configuration(current['data']):
            raise ValueError('자료 선택이 변경됐습니다.')
        data = deepcopy(current['data'])
        output = data['outputs'][job['output']]
        if output.get('fileId') != body['file_id'] or output.get('changed'):
            raise ValueError('최신 제작 파일을 확인하세요.')
        output.update(complete=True, changed=False, archiveStatus='uploaded')
        saved = client._request('POST', '/rest/v1/rpc/media_confirm_job', json={'p_id': job['id'],
            'p_file_id': body['file_id'], 'p_revision': body['revision'], 'p_catalog_revision': snapshot['catalog_revision']})
        return handler.reply(200, client._current(saved))

    def upload_start(self, client, member, body):
        from urllib.parse import quote, urlsplit
        from ..web.original.onedrive import valid_id
        filename, size, digest = body['filename'], body['size'], body['digest']
        if (not isinstance(filename, str) or Path(filename).name != filename or '/' in filename or '\\' in filename
                or len(filename)>255 or Path(filename).suffix.lower() not in ('.ppt','.pptx','.mp4','.mp3','.wav','.pdf')
                or type(size) is not int or not 0<size<=128*1024*1024
                or not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest)):
            raise ValueError('파일명·지원 형식·크기를 확인하세요.')
        route, query = body['route'], body['query']
        if route not in ('/api/attachments','/api/song-assets') or not isinstance(query,dict):
            raise ValueError('업로드 위치를 확인하세요.')
        if route == '/api/attachments':
            day, service, slot = query['date'], query['service'], query['slot']
            if not isinstance(slot,str) or not 0<len(slot)<=200:
                raise ValueError('예배 항목을 확인하세요.')
            snapshot = self.catalog(client,day,service)
            if not compatible_original(filename,service,snapshot['work']['data'].get('fridayMode','zoom'),slot):
                raise ValueError('예배 방식과 맞는 자료를 선택하세요.')
            operation, mutation = 'attachment', {'day':day,'service':service,'slot':slot}
        else:
            snapshot = self.catalog(client)
            operation, mutation = 'song_asset', {'replace_digest':query.get('replace_digest')}
        mutation.update(song_id=query.get('song_id'),filename=filename,digest=digest)
        if mutation['song_id'] and not any(row['id']==mutation['song_id'] for row in snapshot['tables']['songs']):
            raise ValueError('등록 곡을 확인하세요.')
        folder = self.cloud.selected('source')
        name = 'original-'+uuid4().hex+'-'+filename
        session = self.cloud.graph('/me/drive/items/'+valid_id(folder['id'])+':/'+quote(name,safe='')+':/createUploadSession',
            method='POST',body={'item':{'@microsoft.graph.conflictBehavior':'fail','name':name}})
        upload_url = session['uploadUrl']
        parts = urlsplit(upload_url)
        if (parts.scheme!='https' or parts.username or parts.password or parts.port not in (None,443)
                or not any(parts.hostname==d or (parts.hostname or '').endswith('.'+d)
                           for d in ('1drv.com','onedrive.com','sharepoint.com','microsoftpersonalcontent.com'))):
            raise ValueError('Microsoft 업로드 주소를 확인하지 못했습니다.')
        state = {'purpose':'media-source-upload-v1','expires':int(time.time())+1800,'user_id':member.user_id,
                 'operation':operation,'mutation':mutation,'catalog_revision':snapshot['catalog_revision'],
                 'size':size,'name':name,'folder_id':folder['id']}
        sealed = self.sessions.cipher.encrypt(json.dumps(state).encode()).decode()
        # Scoped upload capability, never a Microsoft account OAuth token.
        return {'upload_url':upload_url,'sealed':sealed,'chunk_size':5*1024*1024}

    def upload_finish(self, client, member, body):
        state=json.loads(self.sessions.cipher.decrypt(body['sealed'].encode()))
        if (state.get('purpose')!='media-source-upload-v1' or state['expires']<time.time()
                or state['user_id']!=member.user_id):
            raise ValueError('업로드 확인 시간이 만료됐습니다.')
        item=self.cloud.item(body['item_id'])
        if item.get('name')!=state['name'] or item.get('parentReference',{}).get('id')!=state['folder_id']:
            raise ValueError('선택한 원본 위치를 확인하세요.')
        record={'digest':state['mutation']['digest'],'filename':state['mutation']['filename'],'size':state['size'],
                'item_id':item['id'],'drive_id':item['parentReference']['driveId']}
        with tempfile.TemporaryDirectory(prefix='media-source-check-') as folder:
            download_verified(self.cloud,record,Path(folder)/'source','source')
        self.backend.call('media_register_file',{'p_record':record})
        self.edit(client,{'catalog_revision':state['catalog_revision']},state['operation'],state['mutation'])
        return {**state['mutation'],'archive_status':'uploaded','duplicate':False}

    @staticmethod
    def with_results(client, day, service, current):
        current=deepcopy(current)
        for job in client.list(day,service):
            if job['status']!='succeeded':continue
            original=job['input']
            if (original.get('fields')!=current['data'].get('fields')
                    or render_configuration(original)!=render_configuration(current['data'])):continue
            kind=job['output'];result=job['result']
            outputs=current['data'].setdefault('outputs',{})
            # Keep an explicitly saved newer output or its completed review state.
            if outputs.get(kind,{}).get('fileId'):continue
            outputs[kind]={'generated':True,'complete':False,'changed':False,
                'fileId':result['file_id'],'filename':result['filename'],'unresolved':result['unresolved'],
                'format':'pdf' if kind=='pdf' else 'pptx','engineVersion':result.get('engine_version'),
                'typographyVersion':result.get('typography_version'),'layoutVersion':result.get('layout_version')}
        return current

    def onedrive(self, handler, client, parsed):
        from ..web.original.onedrive import OneDrive
        action=parsed.path.removeprefix('/api/onedrive/')
        query=parse_qs(parsed.query)
        if action=='status' and handler.command=='GET':
            return handler.reply(200,self.cloud.status('https://'+handler.headers['Host']))
        if action=='files' and handler.command=='GET':
            purpose=query.get('purpose',['source'])[0]
            if purpose not in ('source','archive'):raise ValueError('자료 종류를 확인하세요.')
            return handler.reply(200,{'items':self.cloud.list_selected(purpose,query.get('id',[None])[0],query.get('q',[''])[0])})
        if action=='folders' and handler.command=='GET':
            return handler.reply(200,{'items':[i for i in self.cloud.children(query.get('id',['root'])[0]) if 'folder' in i]})
        if action=='download' and handler.command=='GET':
            item=self.cloud.item(query['id'][0])
            if ('file' not in item or not self.cloud.within(item,self.cloud.selected('archive'))
                    or not 0<item.get('size',0)<=512*1024*1024):raise ValueError('완료본 폴더의 파일을 선택하세요.')
            content=self.cloud._download(item)
            if len(content)!=item['size']:raise ValueError('파일 전송 크기를 확인하세요.')
            with tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/item['name'];path.write_bytes(content)
                return send_download(handler,path)
        if handler.command!='POST':raise ValueError('요청 방식을 확인하세요.')
        body=self.body(handler,16384)
        if action=='upload-source':
            snapshot=self.catalog(client)
            row=next((r for r in snapshot['tables']['files'] if r['digest']==body['digest']),None)
            if row is None:raise ValueError('등록 원본을 확인하세요.')
            item=self.cloud.item(row['item_id'])
            if not self.cloud.within(item,self.cloud.selected('source')):raise ValueError('원본 폴더를 확인하세요.')
            return handler.reply(200,{'uploaded':True,'digest':row['digest']})
        if action=='archive':
            current=client.get(body['date'],body['service'])
            output=current['data'].get('outputs',{}).get(body['kind'],{})
            if output.get('complete') is not True:raise ValueError('최신 파일 검수를 완료하세요.')
            job=client.artifact_job(output['fileId'])
            return handler.reply(200,{'work':current,'item':job['result']['artifact'],'already_archived':True})
        if action=='import':
            return handler.reply(201,self.import_original(client,body['id'],body['song_id']))
        if action=='auto-connect':
            snapshot=self.catalog(client)
            songs=self.songs(snapshot)
            records={r['item_id']:r for r in snapshot['tables']['files']}
            registered={(r['song_id'],r['digest']) for r in snapshot['tables']['song_assets']}
            runtime={r['digest'] for r in snapshot['tables']['runtime_assets']}
            pending=[self.cloud.selected('source')['id']];seen=set();groups={}
            result={'linked':0,'unchanged':0,'pending':0,'choices':[],'errors':[]}
            count=0
            while pending:
                identifier=pending.pop()
                if identifier in seen:continue
                seen.add(identifier)
                if len(seen)>200:raise ValueError('원본 폴더가 너무 많습니다.')
                for item in self.cloud.children(identifier):
                    if 'folder' in item:pending.append(item['id']);continue
                    if 'file' not in item:continue
                    count+=1
                    if count>4000:raise ValueError('원본 파일이 너무 많습니다.')
                    known=records.get(item['id'])
                    if known and known['digest'] in runtime:continue
                    if known and known['size']==item.get('size') and any(d==known['digest'] for _,d in registered):
                        old_stamp=known.get('item',{}).get('lastModifiedDateTime')
                        if old_stamp and old_stamp!=item.get('lastModifiedDateTime'):
                            result['choices'].append({'name':item['name'],'reason':'원본 변경 여부를 직접 확인하세요.'})
                        else:result['unchanged']+=1
                        continue
                    if Path(item.get('name','')).suffix.lower() not in ('.ppt','.pptx','.mp3','.mp4','.wav','.pdf'):continue
                    song=OneDrive.filename_song(item['name'],songs)
                    if song:groups.setdefault(song['id'],[]).append(item)
                    else:result['choices'].append({'name':item['name'],'reason':'곡명·찬송가 종류를 직접 선택하세요.'})
            for song_id,items in groups.items():
                if len(items)!=1:
                    result['choices'] += [{'name':i['name'],'reason':'같은 곡의 원본이 여러 개 · 직접 선택'} for i in items]
                    continue
                if result['linked']>=20:result['pending']+=1;continue
                try:
                    self.import_original(client,items[0]['id'],song_id)
                    result['linked']+=1
                except Exception:result['errors'].append({'name':items[0]['name'],'reason':'원본 연결을 완료하지 못했습니다.'})
            return handler.reply(200,result)
        return handler.reply(409,{'error':'연결·폴더 변경은 관리자 배포 설정에서 진행하세요.'})

    def import_original(self,client,item_id,song_id):
        snapshot=self.catalog(client)
        if not any(r['id']==song_id for r in snapshot['tables']['songs']):raise ValueError('등록 곡을 확인하세요.')
        item=self.cloud.item(item_id)
        if ('file' not in item or not self.cloud.within(item,self.cloud.selected('source'))
                or not 0<item.get('size',0)<=128*1024*1024):raise ValueError('원본 폴더의 지원 파일을 선택하세요.')
        content=self.cloud._download(item)
        if len(content)!=item['size']:raise ValueError('원본 파일 크기를 확인하세요.')
        with tempfile.TemporaryDirectory() as folder:
            digest,_,_=WorkStore(Path(folder)/'validate.db')._store_file(item['name'],content)
        record={'digest':digest,'filename':item['name'],'size':item['size'],'item_id':item['id'],
                'drive_id':item['parentReference']['driveId']}
        self.backend.call('media_register_file',{'p_record':record})
        mutation={'song_id':song_id,'filename':item['name'],'digest':digest}
        self.edit(client,snapshot,'song_asset',mutation)
        return {**mutation,'archive_status':'uploaded'}
