"""Cloud job clients: user requests and server-only execution are separated."""
from uuid import UUID

import requests

from .supabase_auth import SupabaseAuth
from .supabase_work_store import SupabaseWorkStore, WorkStoreUnavailable, validate_work
from ..web.original.work_store import RevisionConflict


class JobClient(SupabaseWorkStore):
    def snapshot(self, day, service, revision):
        validate_work(day, service)
        if type(revision) is not int or revision < 0:
            raise ValueError('Invalid revision')
        result = self._request('POST', '/rest/v1/rpc/media_catalog_snapshot', json={
            'p_day': day, 'p_service': service, 'p_revision': revision})
        if not isinstance(result, dict) or type(result.get('matched')) is not bool:
            raise WorkStoreUnavailable('Invalid catalog response')
        if not result['matched']:
            raise RevisionConflict(self._current(result.get('current')))
        if (result.get('day') != day or result.get('service') != service
                or not isinstance(result.get('tables'), dict)
                or self._current(result.get('work'))['revision'] != revision):
            raise WorkStoreUnavailable('Catalog does not match requested work')
        return result

    def list(self, day, service):
        validate_work(day, service)
        return self._request('GET', '/rest/v1/media_jobs', params={'day': 'eq.' + day, 'service': 'eq.' + service,
            'select': 'id,status,result,day,service,revision,output,deadline,created_at,input:snapshot->work->data,catalog_revision:snapshot->catalog_revision', 'order': 'created_at.desc', 'limit': '20'})

    def status(self, identifier):
        rows = self._request('GET', '/rest/v1/media_jobs', params={'id': 'eq.' + str(UUID(identifier)),
            'select': 'id,status,result,day,service,revision,output,deadline', 'limit': '1'})
        if not isinstance(rows, list) or len(rows) != 1:
            raise WorkStoreUnavailable('제작 작업을 찾지 못했습니다.')
        return rows[0]

    def artifact_job(self, file_id):
        if not isinstance(file_id, str) or len(file_id) != 32 or any(c not in '0123456789abcdef' for c in file_id):
            raise ValueError('Invalid artifact ID')
        rows = self._request('GET', '/rest/v1/media_jobs', params={'result->>file_id': 'eq.' + file_id,
            'status': 'eq.succeeded', 'select': 'id,status,result,day,service,revision,output', 'limit': '1'})
        if not isinstance(rows, list) or len(rows) != 1:
            raise WorkStoreUnavailable('완료된 제작 파일을 찾지 못했습니다.')
        return rows[0]

    def cancel(self, identifier):
        return self._request('POST', '/rest/v1/rpc/media_cancel_job', json={'p_id': str(UUID(identifier))})

    def start(self, day, service, revision, output, groups, request_key):
        validate_work(day, service)
        if type(revision) is not int or revision < 1 or output not in ('ppt', 'pdf') or not isinstance(groups, list):
            raise ValueError('Invalid production request')
        key = str(UUID(request_key))
        result = self._request('POST', '/rest/v1/rpc/media_start_job', json={
            'p_day': day, 'p_service': service, 'p_revision': revision,
            'p_output': output, 'p_groups': groups, 'p_request_key': key})
        if isinstance(result, dict) and result.get('matched') is False:
            raise RevisionConflict(self._current(result.get('current')))
        if isinstance(result, dict) and result.get('queued') is False and result.get('busy') is True:
            return result
        if (not isinstance(result, dict) or result.get('queued') is not True
                or result.get('status') not in ('queued','running','succeeded','failed')):
            raise WorkStoreUnavailable('Invalid production queue response')
        try:
            UUID(result['id'])
        except (ValueError, KeyError, TypeError, AttributeError):
            raise WorkStoreUnavailable('Invalid production job ID') from None
        return result


class JobBackend:
    """Only the trusted worker receives this client; never expose it to a browser."""
    def __init__(self, url, secret_key):
        self.url = SupabaseAuth(url, 'sb_publishable_validation_only').url
        if (not isinstance(secret_key, str) or not secret_key.startswith('sb_secret_')
                or any(c.isspace() for c in secret_key)):
            raise ValueError('Server secret key required')
        self._headers = {'apikey': secret_key}

    def call(self, name, body):
        if name not in ('media_claim_job', 'media_finish_job', 'media_job_active', 'media_dispatch_job', 'media_register_file'):
            raise ValueError('Unsupported worker operation')
        try:
            response = requests.post(self.url + '/rest/v1/rpc/' + name, headers=self._headers,
                                     json=body, timeout=(5, 20), allow_redirects=False)
        except requests.RequestException:
            raise WorkStoreUnavailable('Worker operation result unknown') from None
        if response.status_code != 200:
            raise WorkStoreUnavailable('Worker operation failed')
        try:
            return response.json()
        except ValueError:
            raise WorkStoreUnavailable('Invalid worker response') from None

    def claim(self, identifier, execution):
        return self.call('media_claim_job', {'p_id': str(UUID(identifier)), 'p_execution': execution})

    def finish(self, identifier, execution, success, result):
        return self.call('media_finish_job', {'p_id': str(UUID(identifier)), 'p_execution': execution,
                                             'p_success': success, 'p_result': result})
