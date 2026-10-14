"""Read-only Google runtime check of the two selected OneDrive folders.

The imported credential is read once. Token refresh changes stay in memory for
this check; no secret version or OneDrive file is written.
"""
import copy
import json
import os
from types import SimpleNamespace

from .secret_connection import SecretConnection
from ..web.original.onedrive import OneDrive


class MemoryConnection:
    def __init__(self, data):
        self.data = copy.deepcopy(data)

    def read(self):
        return copy.deepcopy(self.data)

    def write(self, data):
        self.data = copy.deepcopy(data)


def inspect_onedrive(resource, secret_factory=None, drive_factory=None):
    result = {'secret_read': False, 'source_folder_access': False,
              'archive_folder_access': False, 'ready': False}
    stage = 'secret'
    try:
        backend = (secret_factory or SecretConnection)(resource)
        connection = backend.read()
        if not connection.get('account') or not connection.get('secret'):
            raise ValueError('Connection incomplete')
        result['secret_read'] = True
        cloud = (drive_factory or OneDrive)(
            SimpleNamespace(path='/tmp/onedrive-probe-unused.db'),
            connection_backend=MemoryConnection(connection))
        for purpose in ('source', 'archive'):
            stage = purpose
            selected = cloud.selected(purpose)
            item = cloud.item(selected['id'])
            if not isinstance(item, dict) or 'folder' not in item or item.get('remoteItem'):
                raise ValueError('Expected own-drive folder')
            result[purpose + '_folder_access'] = True
        result['ready'] = True
    except Exception:
        # SDK/OAuth error text may include credentials. Only print fixed flags.
        result['failed_stage'] = stage
    return result


def main():
    resource = os.environ.get('MEDIA_ONEDRIVE_SECRET', '')
    result = inspect_onedrive(resource)
    print(json.dumps(result))
    return 0 if result['ready'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
