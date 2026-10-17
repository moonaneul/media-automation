"""Revision-checked church work storage via the user's Supabase JWT.

Not a replacement for the local file/asset store. Enable cloud web writes only
after the separate migration and production adapters are ready.
"""
from datetime import date
import json

import requests

from .supabase_auth import AccessDenied, SupabaseAuth
from ..web.original.work_store import RevisionConflict


class WorkStoreUnavailable(Exception):
    """Read failed, or a write's outcome is unknown; never fall back locally."""


def validate_work(day, service, expected_revision=None, data=None):
    if not isinstance(day, str) or date.fromisoformat(day).isoformat() != day:
        raise ValueError('날짜 형식을 확인하세요.')
    if service not in ('wednesday', 'friday', 'sunday'):
        raise ValueError('예배 종류를 확인하세요.')
    if expected_revision is None and data is None:
        return
    if type(expected_revision) is not int or expected_revision < 0 or not isinstance(data, dict):
        raise ValueError('저장 요청 형식을 확인하세요.')
    fields = data.get('fields', {})
    if not isinstance(fields, dict):
        raise ValueError('입력 항목 형식을 확인하세요.')
    for field in fields.values():
        if (not isinstance(field, dict) or field.get('state') not in ('UNSET', 'NONE', 'VALUE')
                or not isinstance(field.get('value', ''), str)):
            raise ValueError('입력 상태를 확인하세요.')
        value = field.get('value', '')
        if (field['state'] == 'VALUE' and not value.strip()) or (field['state'] != 'VALUE' and value):
            raise ValueError('입력값과 상태가 일치하지 않습니다.')
    if len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode()) > 1024 * 1024:
        raise ValueError('입력 내용이 너무 큽니다.')


class SupabaseWorkStore:
    def __init__(self, url, publishable_key, access_token):
        # Shared configuration validation; no admin key and no persistent token.
        config = SupabaseAuth(url, publishable_key)
        if not isinstance(access_token, str) or not access_token or len(access_token) > 16384:
            raise AccessDenied('Login required')
        self.url = config.url
        self._headers = {'apikey': config.key, 'Authorization': 'Bearer ' + access_token}

    def _request(self, method, path, **kwargs):
        try:
            response = requests.request(method, self.url + path, headers=self._headers,
                                        timeout=(5, 15), allow_redirects=False, **kwargs)
        except requests.RequestException:
            raise WorkStoreUnavailable('저장 결과를 확인할 수 없습니다. 다시 불러와 확인하세요.') from None
        if response.status_code in (401, 403):
            raise AccessDenied('Active team membership required')
        if response.status_code != 200:
            # No retries: a timed-out POST may already have committed.
            raise WorkStoreUnavailable('작업 저장 서버 응답을 확인하지 못했습니다.')
        try:
            return response.json()
        except ValueError:
            raise WorkStoreUnavailable('작업 저장 서버 응답을 확인하지 못했습니다.') from None

    @staticmethod
    def _current(value):
        if (not isinstance(value, dict) or type(value.get('revision')) is not int
                or value['revision'] < 0 or not isinstance(value.get('data'), dict)
                or (value.get('updated_at') is not None and not isinstance(value['updated_at'], str))):
            raise WorkStoreUnavailable('잘못된 작업 저장 응답입니다.')
        return {'revision': value['revision'], 'data': value['data'], 'updated_at': value.get('updated_at')}

    def get(self, day, service):
        validate_work(day, service)
        return self._current(self._request('POST', '/rest/v1/rpc/media_get_work', json={
            'p_day': day, 'p_service': service,
        }))

    def save(self, day, service, expected_revision, data):
        # Explicit validation even when data/expected_revision are None.
        if type(expected_revision) is not int or not isinstance(data, dict):
            raise ValueError('저장 요청 형식을 확인하세요.')
        validate_work(day, service, expected_revision, data)
        result = self._request('POST', '/rest/v1/rpc/media_save_work', json={
            'p_day': day, 'p_service': service, 'p_expected_revision': expected_revision, 'p_data': data,
        })
        if not isinstance(result, dict) or type(result.get('saved')) is not bool:
            raise WorkStoreUnavailable('잘못된 작업 저장 응답입니다.')
        current = self._current(result.get('current'))
        if not result['saved']:
            raise RevisionConflict(current)
        if current['revision'] != expected_revision + 1 or current['data'] != data:
            raise WorkStoreUnavailable('저장 결과가 요청한 입력과 일치하지 않습니다.')
        return current
