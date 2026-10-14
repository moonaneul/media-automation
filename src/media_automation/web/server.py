"""Single supported entry point for the original church web application."""
import argparse
import os
from pathlib import Path
from .original.server import make_server as _original_server
from .original.work_store import WorkStore

def make_server(application, port=8765, password=None, public_origin=None, supabase_auth=None):
    # Preserve programmatic job API clients; the executable always runs the original UI.
    if isinstance(application, WorkStore):
        return _original_server(application, port, password, public_origin=public_origin, supabase_auth=supabase_auth)
    from .engine_api import make_server as job_api
    return job_api(application, port)

def default_database(root=None):
    """Use the selected local store; never replace a broken pointer with an empty DB."""
    root = Path.cwd() if root is None else Path(root)
    configured = os.environ.get('MEDIA_DATABASE')
    if configured:
        return Path(configured).expanduser()
    pointer = root / 'output/main-database.txt'
    if pointer.exists():
        value = pointer.read_text().strip()
        if not value:
            raise ValueError('실사용 DB 경로가 비어 있습니다: ' + str(pointer))
        database = Path(value).expanduser()
        if not database.is_absolute():
            database = root / database
        if not database.is_file():
            raise ValueError('지정된 실사용 DB를 찾지 못했습니다: ' + str(database))
        return database
    unified = root / 'output/unified-work/work.db'
    return unified if unified.is_file() else root / 'output/web/work.db'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--import-original', type=Path, help='기존 원본 웹 DB를 새 저장소에 읽기 전용 복사')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--database', type=Path)
    args = parser.parse_args()
    try:
        args.database = args.database.expanduser() if args.database is not None else default_database()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.import_original:
        from .original.migration import snapshot_store
        snapshot_store(args.import_original, args.database)
    args.database.parent.mkdir(parents=True, exist_ok=True)
    password_file = os.environ.get('MEDIA_ACCESS_PASSWORD_FILE')
    password = Path(password_file).read_text().strip() if password_file else os.environ.get('MEDIA_ACCESS_PASSWORD')
    public_origin = os.environ.get('MEDIA_PUBLIC_ORIGIN')
    supabase_auth = None
    if os.environ.get('MEDIA_AUTH_PROVIDER') == 'supabase':
        import json
        from ..cloud.supabase_auth import SupabaseAuth
        config_path = Path(__file__).resolve().parents[3] / 'deploy/cloud/supabase-public.json'
        config = json.loads(config_path.read_text())
        supabase_auth = SupabaseAuth(config['url'], config['publishable_key'])
    elif os.environ.get('MEDIA_AUTH_PROVIDER') not in (None, '', 'local'):
        parser.error('Unknown MEDIA_AUTH_PROVIDER')
    server = make_server(WorkStore(args.database), args.port, password, public_origin, supabase_auth)
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
