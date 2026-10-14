"""Interactive connection check. Never persist or print passwords or tokens."""
import getpass
import json
from pathlib import Path
import sys

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from media_automation.cloud.supabase_auth import AccessDenied, AuthUnavailable, SupabaseAuth


def main():
    config = json.loads((ROOT / 'deploy/cloud/supabase-public.json').read_text())
    auth = SupabaseAuth(config['url'], config['publishable_key'])
    email = input('Supabase에 등록한 로그인 이메일: ').strip()
    if not sys.stdin.isatty():
        print('비밀번호 보호를 위해 직접 터미널에서 실행해 주세요.')
        return 1
    password = getpass.getpass('웹사이트 로그인 비밀번호(입력 중 표시 안 됨): ')
    try:
        response = requests.post(
            config['url'] + '/auth/v1/token', params={'grant_type': 'password'},
            headers={'apikey': config['publishable_key']},
            json={'email': email, 'password': password},
            timeout=(5, 15), allow_redirects=False,
        )
        password = None
        if response.status_code != 200:
            print('로그인 실패. 이메일·비밀번호·계정 확인 상태를 확인하세요. HTTP', response.status_code)
            return 1
        data = response.json()
        token = data.get('access_token')
        if not isinstance(token, str) or not token:
            print('로그인 응답을 확인할 수 없습니다.')
            return 1
        try:
            member = auth.authenticate('Bearer ' + token)
            print('로그인 및 미디어팀 권한 확인 성공')
            print('사용자 UID:', member.user_id)
            print('권한:', member.role)
        finally:
            # Revoke this check's session only, leaving other logins untouched.
            try:
                logout = requests.post(
                    config['url'] + '/auth/v1/logout', params={'scope': 'local'},
                    headers={'apikey': config['publishable_key'], 'Authorization': 'Bearer ' + token},
                    timeout=(5, 10), allow_redirects=False,
                )
                if logout.status_code not in (200, 204):
                    print('시험 세션 종료는 확인되지 않았습니다. 인증정보는 파일에 저장하지 않았습니다.')
            except requests.RequestException:
                print('시험 세션 종료는 확인되지 않았습니다. 인증정보는 파일에 저장하지 않았습니다.')
    except (requests.RequestException, ValueError, AccessDenied, AuthUnavailable):
        print('연결 또는 팀원 권한 확인에 실패했습니다. 비밀번호·토큰은 공유하지 마세요.')
        return 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (KeyboardInterrupt, EOFError):
        print('\n로그인 확인을 취소했습니다.')
        raise SystemExit(1)
