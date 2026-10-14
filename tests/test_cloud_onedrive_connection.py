import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from media_automation.cloud.connection_bundle import encrypt_connection, decrypt_connection
from media_automation.cloud.secret_connection import SecretConnection
from media_automation.web.original.onedrive import CloudError, OneDrive

RESOURCE = 'projects/church-media-511519/secrets/church-media-onedrive'
DATA = {'client_id': 'test-client', 'secret': 'private-client-secret',
        'cache': 'private-refresh-token', 'account': {'username': 'test@example.com'},
        'folders': {'source': {'id': 'source'}, 'archive': {'id': 'archive'}}}
PASSWORD = 'a-long-transfer-passphrase'


def version(number, data=DATA):
    return SimpleNamespace(name=RESOURCE + '/versions/' + str(number),
                           payload=SimpleNamespace(data=json.dumps(data, ensure_ascii=False).encode()))


def test_encrypted_bundle_preserves_connection_without_plaintext_credentials():
    blob = encrypt_connection(DATA, PASSWORD)
    assert b'private-client-secret' not in blob and b'private-refresh-token' not in blob
    assert decrypt_connection(blob, PASSWORD) == DATA
    assert blob != encrypt_connection(DATA, PASSWORD)


def test_wrong_password_or_modified_bundle_does_not_disclose_connection():
    blob = encrypt_connection(DATA, PASSWORD)
    with pytest.raises(ValueError) as error:
        decrypt_connection(blob, PASSWORD + 'wrong')
    assert 'private' not in str(error.value)
    parsed = json.loads(blob); parsed['token'] = parsed['token'][:-12] + 'A' * 12
    with pytest.raises(ValueError):
        decrypt_connection(json.dumps(parsed).encode(), PASSWORD)


def test_short_passphrase_is_rejected():
    with pytest.raises(ValueError):
        encrypt_connection(DATA, 'short')


def test_backend_reads_and_writes_using_service_identity_client():
    client = Mock(); client.access_secret_version.return_value = version(1)
    client.add_secret_version.return_value = SimpleNamespace(name=RESOURCE + '/versions/2')
    backend = SecretConnection(RESOURCE, client)
    assert backend.read() == DATA
    new = dict(DATA, cache='new-cache')
    backend.write(new)
    request = client.add_secret_version.call_args.kwargs['request']
    assert request['parent'] == RESOURCE
    assert json.loads(request['payload']['data']) == new
    assert client.add_secret_version.call_args.kwargs['retry'] is None
    assert backend.version.endswith('/2')


def test_unchanged_connection_does_not_add_billable_version():
    client = Mock(); client.access_secret_version.return_value = version(1)
    backend = SecretConnection(RESOURCE, client)
    backend.read(); backend.write(DATA)
    client.add_secret_version.assert_not_called()


def test_detected_stale_connection_never_overwrites_newer_version():
    client = Mock(); client.access_secret_version.side_effect = [version(1), version(2)]
    backend = SecretConnection(RESOURCE, client)
    backend.read()
    with pytest.raises(CloudError):
        backend.write(dict(DATA, cache='stale-cache'))
    client.add_secret_version.assert_not_called()


def test_secret_failure_never_returns_raw_credentials():
    client = Mock(); client.access_secret_version.side_effect = RuntimeError('private-refresh-token')
    with pytest.raises(CloudError) as error:
        SecretConnection(RESOURCE, client).read()
    assert 'private-refresh-token' not in str(error.value)


def test_injected_backend_does_not_create_local_credentials(tmp_path):
    backend = Mock(); backend.read.return_value = DATA
    cloud = OneDrive(SimpleNamespace(path=str(tmp_path / 'work.db')), connection_backend=backend)
    assert cloud._read() == DATA
    cloud._write(DATA)
    backend.write.assert_called_once_with(DATA)
    assert not cloud.folder.exists()
