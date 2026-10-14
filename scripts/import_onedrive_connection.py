"""Cloud Shell importer. Decrypted credentials go directly to gcloud stdin."""
import argparse
import getpass
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.cloud.connection_bundle import decrypt_connection


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--file', type=Path, required=True)
    parser.add_argument('--project', default='church-media-511519')
    parser.add_argument('--secret', default='church-media-onedrive')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', args.project) or not re.fullmatch(r'[A-Za-z0-9_-]{1,255}', args.secret):
        print('프로젝트 또는 비밀 저장소 이름을 확인하세요.')
        return 1
    if not sys.stdin.isatty():
        print('직접 Cloud Shell 터미널에서 실행하세요.')
        return 1
    if not args.file.is_file() or args.file.stat().st_size > 128 * 1024:
        print('암호화 전달 파일을 확인하세요.')
        return 1
    password = getpass.getpass('맥에서 정한 전달용 암호(입력 표시 안 됨): ')
    try:
        connection = decrypt_connection(args.file.read_bytes(), password)
    except ValueError:
        print('암호 또는 암호화 파일을 확인하세요.')
        return 1
    prefix = ['gcloud', 'secrets']
    # Never overwrite an existing connection. Initial bootstrap only.
    created = subprocess.run(prefix + ['create', args.secret, '--project', args.project,
        '--replication-policy=automatic', '--quiet'], capture_output=True)
    if created.returncode:
        print('새 비밀 저장소를 만들지 못했습니다. 기존 저장소 여부와 프로젝트 권한을 확인하세요.')
        return 1
    added = subprocess.run(prefix + ['versions', 'add', args.secret, '--project', args.project,
        '--data-file=-', '--format=value(name)', '--quiet'],
        input=json.dumps(connection, ensure_ascii=False, allow_nan=False).encode(), capture_output=True)
    if added.returncode:
        print('연결 정보 저장 결과를 확인하지 못했습니다. 자동으로 재시도하지 않습니다.')
        return 1
    print('Google 비밀 저장소에 OneDrive 연결 정보 저장 완료')
    print('프로젝트:', args.project)
    print('비밀 저장소:', args.secret)
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\n전달을 취소했습니다.')
        raise SystemExit(1)
