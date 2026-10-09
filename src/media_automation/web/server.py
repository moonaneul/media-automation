from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
from urllib.parse import parse_qs, urlsplit
from .application import Application

MAX_UPLOAD = 128 * 1024 * 1024
STATIC = Path(__file__).parent / 'static'


def make_server(application: Application, port: int = 8765):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Avoid logging file paths or credentials.

        def reply(self, status, body, content_type='application/json; charset=utf-8'):
            data = json.dumps(body, ensure_ascii=False).encode() if isinstance(body, (dict, list)) else body
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'; object-src 'none'")
            self.end_headers()
            self.wfile.write(data)

        def handle_request(self):
            expected = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected:
                self.reply(403, {'error': '로컬 주소로 접속해주세요.'})
                return
            parsed = urlsplit(self.path)
            path = parsed.path
            if self.command == 'GET' and path in {'/', '/app.js', '/style.css'}:
                file = STATIC / ({'/':'index.html'}.get(path, path[1:]))
                self.reply(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or 'text/plain')
                return
            if not secrets.compare_digest(self.headers.get('Authorization', ''), 'Bearer ' + token):
                self.reply(401, {'error': '실행 시 표시된 접속 링크를 이용해주세요.'})
                return
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + expected:
                self.reply(403, {'error': '다른 사이트의 요청은 허용하지 않습니다.'})
                return
            try:
                query = parse_qs(parsed.query)
                parts = path.strip('/').split('/')
                if self.command == 'GET' and path == '/api/jobs':
                    self.reply(200, application.list())
                elif self.command == 'POST' and path == '/api/jobs':
                    data = self.body_json()
                    self.reply(201, application.create(data['service'], data['date']))
                elif len(parts) >= 3 and parts[:2] == ['api', 'jobs']:
                    job = parts[2]
                    if self.command == 'GET' and len(parts) == 3:
                        self.reply(200, application.get(job))
                    elif self.command == 'GET' and parts[3:] == ['sunday-common']:
                        self.reply(200, application.sunday_common_summary(job))
                    elif self.command == 'POST' and parts[3:] == ['import-sunday-week']:
                        self.reply(200, application.import_sunday_week(job, self.body_json()['sunday_job_id']))
                    elif self.command == 'GET' and parts[3:] == ['notice-preview']:
                        self.reply(200, application.notice_preview(job))
                    elif self.command == 'POST' and parts[3:] == ['confirm-notice']:
                        self.reply(200, application.confirm_notice(job))
                    elif self.command == 'GET' and parts[3:] == ['input-types']:
                        self.reply(200, application.catalog(job))
                    elif self.command == 'POST' and parts[3:] == ['typed-files']:
                        self.reply(201, application.upload_typed(
                            job, query['kind'][0], query['filename'][0],
                            self.body(MAX_UPLOAD), query.get('slot', [None])[0]))
                    elif self.command == 'POST' and parts[3:] == ['bulletin-number']:
                        self.reply(200, application.set_bulletin_number(
                            job, self.body_json()['number']))
                    elif self.command == 'POST' and parts[3:] == ['files']:
                        self.reply(201, application.upload(job, query['path'][0], self.body(MAX_UPLOAD)))
                    elif self.command == 'POST' and parts[3:] == ['run']:
                        self.reply(202, application.start(job, self.body_json().get('source')))
                    elif self.command == 'GET' and parts[3:] == ['artifact']:
                        target = application.artifact(job, query['path'][0])
                        self.reply(200, target.read_bytes(), mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
                    else:
                        self.reply(404, {'error': '없는 경로입니다.'})
                else:
                    self.reply(404, {'error': '없는 경로입니다.'})
            except (ValueError, KeyError, FileExistsError, FileNotFoundError, RuntimeError) as exc:
                self.reply(400, {'error': str(exc)})
            except Exception:
                self.reply(500, {'error': '서버 처리 오류. 로컬 상태를 확인해주세요.'})

        def body(self, limit):
            count = int(self.headers.get('Content-Length', '-1'))
            if count < 0 or count > limit:
                raise ValueError('파일 크기 제한을 초과했거나 크기가 없습니다.')
            data = self.rfile.read(count)
            if len(data) != count:
                raise ValueError('파일 업로드가 중단되었습니다.')
            return data

        def body_json(self):
            data = json.loads(self.body(16384))
            if not isinstance(data, dict):
                raise ValueError('객체 형식의 입력이 필요합니다.')
            return data

        do_GET = handle_request
        do_POST = handle_request

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    return server, token


def main():
    parser = argparse.ArgumentParser(description='맥 로컬 미디어 제작 화면')
    parser.add_argument('--repository', type=Path, default=Path.cwd())
    parser.add_argument('--storage', type=Path, default=Path.home() / 'Library/Application Support/media-automation/jobs')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    application = Application(args.repository, args.storage)
    application.recover()
    server, token = make_server(application, args.port)
    print(f'접속: http://127.0.0.1:{server.server_port}/#{token}', flush=True)
    print('이 창을 유지하세요. 종료는 Ctrl+C. 개인 맥의 신뢰된 자료용입니다.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
