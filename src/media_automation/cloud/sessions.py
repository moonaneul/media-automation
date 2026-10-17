"""Opaque cookies with encrypted, shared, revocable server-side sessions."""
import hashlib
import json
import secrets
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet
import requests

from .supabase_auth import AuthUnavailable


class Sessions:
    def __init__(self, url, secret, key):
        self.url = url
        self.headers = {'apikey': secret}
        self.cipher = Fernet(key)

    def _request(self, method, **kwargs):
        try:
            response = requests.request(method, self.url + '/rest/v1/media_sessions',
                headers={**self.headers, 'Prefer': 'return=representation'}, timeout=(5, 15),
                allow_redirects=False, **kwargs)
            if response.status_code not in (200, 201):
                raise ValueError()
            result = response.json()
            if not isinstance(result, list):
                raise ValueError()
            return result
        except (requests.RequestException, ValueError):
            raise AuthUnavailable('Shared session storage unavailable') from None

    @staticmethod
    def identifier(cookie):
        if not isinstance(cookie, str) or len(cookie) != 43 or not all(c.isalnum() or c in '-_' for c in cookie):
            return None
        return hashlib.sha256(cookie.encode()).hexdigest()

    def create(self, token, member):
        if not isinstance(token, str) or not 0 < len(token) <= 16384:
            raise AuthUnavailable('Invalid upstream session')
        cookie = secrets.token_urlsafe(32)
        expires = int(time.time()) + 3600
        value = {'purpose': 'media-http-session-v1', 'token': token, 'expires': expires, 'user_id': member.user_id}
        self._request('DELETE', params={'expires_at': 'lt.' + datetime.now(timezone.utc).isoformat()})
        rows = self._request('POST', json={'id': self.identifier(cookie), 'user_id': member.user_id,
            'expires_at': datetime.fromtimestamp(expires, timezone.utc).isoformat(),
            'ciphertext': self.cipher.encrypt(json.dumps(value).encode()).decode()})
        if len(rows) != 1:
            raise AuthUnavailable('Session was not saved')
        return cookie

    def read(self, cookie):
        identifier = self.identifier(cookie)
        if identifier is None:
            return None
        rows = self._request('GET', params={'id': 'eq.' + identifier, 'select': 'ciphertext,user_id', 'limit': '1'})
        if not rows:
            return None
        try:
            value = json.loads(self.cipher.decrypt(rows[0]['ciphertext'].encode()))
            if (value['purpose'] != 'media-http-session-v1' or value['user_id'] != rows[0]['user_id']
                    or type(value['expires']) is not int or value['expires'] <= time.time()
                    or not isinstance(value['token'], str) or not 0 < len(value['token']) <= 16384):
                return None
            return value['token']
        except Exception:
            return None

    def delete(self, cookie):
        identifier = self.identifier(cookie)
        if identifier:
            self._request('DELETE', params={'id': 'eq.' + identifier})
