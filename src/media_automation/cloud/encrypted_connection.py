"""Encrypted OneDrive state in Supabase with atomic revision comparison.

Google keeps a fixed encryption key. Updating the token cache does not create
new Google secret versions. Both the backend API key and cipher key are runtime
credentials and must never be sent to a browser.
"""
import json
from datetime import datetime, timezone
import threading

from cryptography.fernet import Fernet
import requests

from .supabase_auth import SupabaseAuth
from ..web.original.onedrive import CloudError


class EncryptedConnection:
    def __init__(self, url, secret_key, cipher_key, bootstrap=None):
        self.url = SupabaseAuth(url, 'sb_publishable_validation_only').url
        if not isinstance(secret_key, str) or not secret_key.startswith('sb_secret_') or any(c.isspace() for c in secret_key):
            raise ValueError('Server secret key required')
        self._headers = {'apikey': secret_key}
        self._cipher = Fernet(cipher_key)
        self.bootstrap = bootstrap
        self.revision = None
        self.lock = threading.RLock()

    def _request(self, method, params=None, body=None, prefer=None):
        headers = dict(self._headers)
        if prefer: headers['Prefer'] = prefer
        try:
            response = requests.request(method, self.url + '/rest/v1/media_connections',
                params=params, json=body, headers=headers, timeout=(5, 15), allow_redirects=False)
        except requests.RequestException:
            raise CloudError('클라우드 연결 저장 결과를 확인하지 못했습니다.') from None
        if response.status_code not in (200, 201):
            raise CloudError('클라우드 연결 저장소에 접근하지 못했습니다.')
        try:
            value = response.json()
            if not isinstance(value, list): raise ValueError()
            return value
        except ValueError:
            raise CloudError('클라우드 연결 저장소 응답을 확인하지 못했습니다.') from None

    def _encode(self, data):
        encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        if len(encoded) > 64 * 1024: raise CloudError('연결 정보 크기를 확인하세요.')
        return self._cipher.encrypt(encoded).decode()

    def read(self):
        with self.lock:
            params = {'id': 'eq.onedrive', 'select': 'revision,ciphertext', 'limit': '1'}
            rows = self._request('GET', params=params)
            if not rows:
                if self.bootstrap is None: raise CloudError('초기 OneDrive 연결 정보가 없습니다.')
                initial = self.bootstrap()
                self._request('POST', body={'id': 'onedrive', 'revision': 1, 'ciphertext': self._encode(initial)},
                    prefer='resolution=ignore-duplicates,return=representation')
                # Another process may have initialized the same row; use its committed value.
                rows = self._request('GET', params=params)
            try:
                if len(rows) != 1 or type(rows[0]['revision']) is not int or rows[0]['revision'] < 1:
                    raise ValueError()
                value = json.loads(self._cipher.decrypt(rows[0]['ciphertext'].encode()))
                if not isinstance(value, dict) or not isinstance(value.get('client_id'), str): raise ValueError()
            except Exception:
                raise CloudError('OneDrive 연결 정보를 해독하지 못했습니다. 서버 암호화 키를 확인하세요.') from None
            self.revision = rows[0]['revision']
            return value

    def write(self, data):
        with self.lock:
            if self.revision is None: raise CloudError('연결 정보를 먼저 읽어야 합니다.')
            rows = self._request('PATCH', params={'id': 'eq.onedrive', 'revision': 'eq.' + str(self.revision)},
                body={'revision': self.revision + 1, 'ciphertext': self._encode(data),
                      'updated_at': datetime.now(timezone.utc).isoformat()},
                prefer='return=representation')
            if len(rows) != 1 or rows[0].get('revision') != self.revision + 1:
                raise CloudError('다른 작업에서 OneDrive 연결이 갱신됐습니다. 다시 시도하세요.')
            self.revision = rows[0]['revision']
