"""Create an encrypted transfer file; credentials never print or go in arguments."""
import argparse
import getpass
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.cloud.connection_bundle import encrypt_connection, decrypt_connection
from media_automation.web.original.onedrive import OneDrive, CloudError


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / 'output/cloud-transfer/onedrive-transfer.enc')
    args = parser.parse_args()
    if not sys.stdin.isatty():
        print('직접 터미널에서 실행하세요. 암호는 명령줄에 넣지 마세요.')
        return 1
    if args.output.exists():
        print('기존 전달 파일이 있습니다. 덮어쓰지 않았습니다.')
        return 1
    password = getpass.getpass('새 전달용 암호(16자 이상, 입력 표시 안 됨): ')
    if password != getpass.getpass('전달용 암호 다시 입력: '):
        print('두 암호가 다릅니다.')
        return 1
    try:
        database = Path((ROOT / 'output/main-database.txt').read_text().strip())
        cloud = OneDrive(SimpleNamespace(path=str(database)))
        connection = cloud._read()
        blob = encrypt_connection(connection, password)
        if decrypt_connection(blob, password) != connection:
            raise ValueError("암호화 검증 실패")
        args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as file:
            file.write(blob)
    except (ValueError, CloudError, OSError):
        print('암호화 전달 파일을 만들지 못했습니다. 연결 상태와 암호 길이를 확인하세요.')
        return 1
    print('암호화·해독 확인 성공')
    print('암호화 파일 생성 완료:', args.output)
    print('전달용 암호는 본인이 보관하세요. 비밀번호·토큰·암호를 채팅에 보내지 마세요.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\n암호화 전달을 취소했습니다.')
        raise SystemExit(1)
