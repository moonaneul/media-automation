"""Single supported entry point for the original church web application."""
import argparse
import os
from pathlib import Path
from .original.server import make_server as _original_server
from .original.work_store import WorkStore

def make_server(application, port=8765, password=None, public_origin=None):
    # Preserve programmatic job API clients; the executable always runs the original UI.
    if isinstance(application, WorkStore):
        return _original_server(application, port, password, public_origin=public_origin)
    from .engine_api import make_server as job_api
    return job_api(application, port)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--import-original', type=Path, help='기존 원본 웹 DB를 새 저장소에 읽기 전용 복사')
    parser.add_argument('--port', type=int, default=8765)
    unified = Path('output/unified-work/work.db')
    default_database = unified if unified.is_file() else Path('output/web/work.db')
    parser.add_argument('--database', type=Path, default=Path(os.environ.get('MEDIA_DATABASE', str(default_database))))
    args = parser.parse_args()
    if args.import_original:
        from .original.migration import snapshot_store
        snapshot_store(args.import_original, args.database)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    password_file = os.environ.get('MEDIA_ACCESS_PASSWORD_FILE')
    password = Path(password_file).read_text().strip() if password_file else os.environ.get('MEDIA_ACCESS_PASSWORD')
    public_origin = os.environ.get('MEDIA_PUBLIC_ORIGIN')
    server = make_server(WorkStore(args.database), args.port, password, public_origin)
    if public_origin:
        print(f'HTTPS 프록시 접속 주소: {public_origin}', flush=True)
    print(f'교회 미디어 작업: http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
