"""Execute only the configured Cloud Run job, passing a validated queue UUID."""
import re
from uuid import UUID

from .supabase_work_store import WorkStoreUnavailable


class Dispatcher:
    def __init__(self, resource, backend, http=None):
        if not re.fullmatch(r'projects/[a-z0-9-]+/locations/[a-z0-9-]+/jobs/[a-z0-9-]+', resource):
            raise ValueError('Invalid configured worker resource')
        self.resource = resource
        self.backend = backend
        self.http = http

    def start(self, identifier):
        identifier = str(UUID(identifier))
        claimed = self.backend.call('media_dispatch_job', {'p_id': identifier})
        if not isinstance(claimed, dict) or claimed.get('dispatch') is not True:
            return False
        http = self.http
        if http is None:
            import google.auth
            from google.auth.transport.requests import AuthorizedSession
            credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
            http = AuthorizedSession(credentials)
        try:
            response = http.post('https://run.googleapis.com/v2/' + self.resource + ':run',
                json={'overrides': {'containerOverrides': [{'name': 'worker', 'env': [
                    {'name': 'MEDIA_JOB_ID', 'value': identifier}]}], 'taskCount': 1}},
                timeout=(5, 20), allow_redirects=False)
            if response.status_code != 200:
                raise ValueError()
        except Exception:
            # The execution may exist already. Do not dispatch a second execution.
            raise WorkStoreUnavailable('제작 실행 결과를 확인하지 못했습니다. 작업 상태를 확인하세요.') from None
        return True
