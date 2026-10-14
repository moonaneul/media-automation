import json
from unittest.mock import Mock

from media_automation.cloud.onedrive_probe import inspect_onedrive, MemoryConnection

RESOURCE = 'projects/church-media-511519/secrets/church-media-onedrive'
CONNECTION = {'account': {'username': 'private-account'}, 'secret': 'private-secret',
              'cache': 'private-token', 'folders': {'source': {'id': 'a'}, 'archive': {'id': 'b'}}}


def test_reads_only_the_two_folder_metadata_and_never_writes_secret():
    secret = Mock(); secret.read.return_value = CONNECTION
    factory = Mock(return_value=secret)
    drive = Mock()
    drive.selected.side_effect = [{'id': 'a'}, {'id': 'b'}]
    drive.item.return_value = {'folder': {}, 'id': 'a'}
    drive_factory = Mock(return_value=drive)
    result = inspect_onedrive(RESOURCE, factory, drive_factory)
    assert result['ready'] is True
    assert drive.item.call_count == 2
    secret.write.assert_not_called()
    backend = drive_factory.call_args.kwargs['connection_backend']
    backend.write(dict(CONNECTION, cache='refreshed-token'))
    assert CONNECTION['cache'] == 'private-token'
    assert 'private' not in json.dumps(result)


def test_secret_error_is_sanitized():
    factory = Mock(side_effect=RuntimeError('private-token'))
    result = inspect_onedrive(RESOURCE, factory)
    assert result['ready'] is False and result['failed_stage'] == 'secret'
    assert 'private-token' not in json.dumps(result)


def test_invalid_folder_fails_without_exposing_metadata():
    secret = Mock(); secret.read.return_value = CONNECTION
    drive = Mock(); drive.selected.return_value = {'id': 'a'}
    drive.item.return_value = {'name': 'private-filename', 'file': {}}
    result = inspect_onedrive(RESOURCE, Mock(return_value=secret), Mock(return_value=drive))
    assert result['failed_stage'] == 'source' and not result['ready']
    assert 'private' not in json.dumps(result)


def test_memory_backend_does_not_mutate_original_or_returned_objects():
    backend = MemoryConnection(CONNECTION)
    returned = backend.read(); returned['account']['username'] = 'changed'
    assert backend.read()['account']['username'] == 'private-account'
