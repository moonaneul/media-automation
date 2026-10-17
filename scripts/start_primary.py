"""Start the single supported local app from its own project directory."""
from pathlib import Path
import argparse
import os
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
PORT = 8876


def main():
    parser = argparse.ArgumentParser(description='통합 미디어 앱 실행')
    parser.add_argument('--check', action='store_true', help='실행 경로와 DB만 확인')
    args = parser.parse_args()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT / 'src'))
    from media_automation.web.server import default_database, main as serve
    try:
        database = default_database(ROOT).resolve()
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print('실사용 폴더:', ROOT, flush=True)
    print('작업 DB:', database, flush=True)
    print(f'접속 주소: http://127.0.0.1:{PORT}/', flush=True)
    if args.check:
        return
    try:
        connection = socket.create_connection(('127.0.0.1', PORT), timeout=1)
    except OSError:
        pass
    else:
        connection.close()
        print('8876 포트가 이미 사용 중입니다. 중복 서버를 시작하지 않습니다.', flush=True)
        return
    os.environ.setdefault('MEDIA_AUTH_PROVIDER', 'supabase')
    sys.argv = [sys.argv[0], '--port', str(PORT), '--database', str(database)]
    serve()


if __name__ == '__main__':
    main()
