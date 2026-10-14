"""Cloud authorization foundation; not yet wired to the local HTTP server."""
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

import requests


class AccessDenied(Exception):
    """Invalid credentials or missing active team membership."""


class AuthUnavailable(Exception):
    """Authentication backend cannot safely answer; deny the request."""


@dataclass(frozen=True)
class Member:
    user_id: str
    role: str


class SupabaseAuth:
    def __init__(self, url: str, publishable_key: str):
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or not parsed.hostname
                or not parsed.hostname.endswith('.supabase.co')
                or parsed.username or parsed.password or parsed.port
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('Expected a hosted Supabase project HTTPS URL')
        if not publishable_key.startswith('sb_publishable_'):
            raise ValueError('Use a Supabase publishable key, never a secret key')
        self.url = url.rstrip('/')
        self.key = publishable_key

    def _get(self, path, token, params=None):
        try:
            response = requests.get(
                self.url + path,
                headers={'apikey': self.key, 'Authorization': 'Bearer ' + token},
                params=params, timeout=(5, 10), allow_redirects=False,
            )
        except requests.RequestException:
            raise AuthUnavailable('Authentication service unavailable') from None
        if response.status_code in (401, 403):
            raise AccessDenied('Sign in with an approved team account')
        if response.status_code != 200:
            raise AuthUnavailable('Authentication service unavailable')
        try:
            return response.json()
        except ValueError:
            raise AuthUnavailable('Invalid authentication response') from None

    def authenticate(self, authorization: str) -> Member:
        if not isinstance(authorization, str):
            raise AccessDenied('Bearer token required')
        parts = authorization.split()
        if (len(parts) != 2 or parts[0].lower() != 'bearer'
                or len(parts[1]) > 16384):
            raise AccessDenied('Bearer token required')
        token = parts[1]
        # Validate remotely: never trust decoded JWT claims or client metadata.
        user = self._get('/auth/v1/user', token)
        try:
            uid = str(UUID(user['id']))
        except (KeyError, TypeError, ValueError, AttributeError):
            raise AccessDenied('Invalid user identity') from None
        rows = self._get('/rest/v1/media_members', token, {
            'select': 'user_id,role,active', 'user_id': 'eq.' + uid, 'limit': '1',
        })
        if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
            raise AccessDenied('Active team membership required')
        row = rows[0]
        if (row.get('user_id') != uid or row.get('active') is not True
                or row.get('role') not in ('admin', 'editor')):
            raise AccessDenied('Active team membership required')
        return Member(uid, row['role'])

    def login(self, email: str, password: str) -> str:
        if not isinstance(email, str) or not email.strip() or not isinstance(password, str) or not password:
            raise AccessDenied('Email and password required')
        try:
            response = requests.post(
                self.url + '/auth/v1/token', params={'grant_type': 'password'},
                headers={'apikey': self.key}, json={'email': email.strip(), 'password': password},
                timeout=(5, 10), allow_redirects=False,
            )
        except requests.RequestException:
            raise AuthUnavailable('Authentication service unavailable') from None
        if response.status_code in (400, 401, 403, 422, 429):
            raise AccessDenied('Check your account credentials')
        if response.status_code != 200:
            raise AuthUnavailable('Authentication service unavailable')
        try:
            token = response.json()['access_token']
            if not isinstance(token, str) or not token:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise AuthUnavailable('Invalid authentication response') from None
        self.authenticate('Bearer ' + token)
        return token
