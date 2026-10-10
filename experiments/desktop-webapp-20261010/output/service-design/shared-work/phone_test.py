"""User-started, password-protected test on a trusted local Wi-Fi network."""
import getpass
import ipaddress
import subprocess
from server import make_server
from work_store import WorkStore
from pathlib import Path


def main():
    print('같은 와이파이 휴대폰 테스트: 인터넷 공개 주소가 아닙니다.')
    print('로컬 HTTP 테스트이므로 신뢰하는 개인 와이파이에서만 사용하세요.')
    print('다른 서비스에서 사용하는 암호를 재사용하지 마세요.')
    suggested = subprocess.run(['ipconfig', 'getifaddr', 'en0'], capture_output=True, text=True).stdout.strip()
    host = input(f'이 컴퓨터의 와이파이 IPv4 주소 [{suggested}]: ').strip() or suggested
    address = ipaddress.ip_address(host)
    if not any(address in ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise SystemExit('사설 와이파이 IPv4 주소가 필요합니다.')
    password = getpass.getpass('이번 테스트용 접속 암호 (12자 이상): ')
    if len(password) < 12:
        raise SystemExit('12자 이상으로 다시 실행하세요.')
    if password != getpass.getpass('접속 암호 확인: '):
        raise SystemExit('암호가 일치하지 않습니다.')
    server = make_server(WorkStore(Path(__file__).with_name('work.db')), 18768, password, host)
    print(f'휴대폰 브라우저 주소: http://{host}:18768/')
    print('이 창을 닫거나 Control+C를 누르면 휴대폰 접속이 종료됩니다.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
