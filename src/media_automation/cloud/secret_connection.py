"""OneDrive connection persistence in Google Secret Manager.

Requires the cloud extra and the runtime's service identity. No service-account
JSON keys. Writers must be serialized across web and job processes before use.
"""
import json
import re
import threading

from ..web.original.onedrive import CloudError


class SecretConnection:
    def __init__(self, resource, client=None):
        if not isinstance(resource, str) or not re.fullmatch(
                r'projects/[a-z0-9][a-z0-9-]*[a-z0-9]/secrets/[A-Za-z0-9_-]+', resource):
            raise ValueError('Expected a Secret Manager secret resource')
        if client is None:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
        self.resource = resource
        self.client = client
        self.lock = threading.RLock()
        self.version = None

    def _latest(self):
        try:
            return self.client.access_secret_version(
                request={'name': self.resource + '/versions/latest'}, timeout=15, retry=None)
        except Exception:
            raise CloudError('클라우드 OneDrive 연결 정보를 읽지 못했습니다.') from None

    def read(self):
        with self.lock:
            version = self._latest()
            try:
                data = json.loads(version.payload.data.decode('utf-8'))
                if not isinstance(data, dict) or not isinstance(data.get('client_id'), str):
                    raise ValueError()
            except (ValueError, TypeError, UnicodeError, AttributeError):
                raise CloudError('클라우드 OneDrive 연결 정보 형식을 확인하세요.') from None
            self.version = version.name
            return data

    def write(self, data):
        with self.lock:
            if not self.version:
                raise CloudError('연결 정보를 먼저 읽어야 합니다.')
            current = self._latest()
            if current.name != self.version:
                raise CloudError('다른 작업에서 OneDrive 연결이 변경됐습니다. 다시 시도하세요.')
            encoded = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            if len(encoded) > 64 * 1024:
                raise CloudError('OneDrive 연결 정보가 비밀 저장소 한도를 초과했습니다.')
            if encoded == current.payload.data:
                return
            try:
                added = self.client.add_secret_version(
                    request={'parent': self.resource, 'payload': {'data': encoded}}, timeout=15, retry=None)
            except Exception:
                # The write may already have committed. Do not repeat it blindly.
                raise CloudError('OneDrive 연결 저장 결과를 확인하지 못했습니다.') from None
            self.version = added.name
            # Version cleanup is a separate explicit maintenance operation.
