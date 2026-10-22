"""Cloud Run worker archives outputs into the service-specific OneDrive folder."""
import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest

from media_automation.cloud.worker import execute


@pytest.mark.parametrize('service,output', [
    ('wednesday', 'ppt'), ('friday', 'ppt'),
    ('sunday', 'ppt'), ('sunday', 'pdf'),
])
def test_worker_archives_artifact_and_preview_in_service_folder(tmp_path, service, output):
    identifier = str(uuid4())
    snapshot = {
        'day': '2026-10-14', 'service': service,
        'work': {'revision': 1}, 'catalog_revision': 2,
    }
    backend = Mock()
    backend.claim.return_value = {
        'claimed': True, 'id': identifier, 'output': output,
        'snapshot': snapshot, 'groups': [],
    }
    backend.call.return_value = {'active': True}
    backend.finish.return_value = {'finished': True}
    cloud = Mock()
    destination = {'id': 'chosen-service-subfolder'}
    cloud.archive_destination.return_value = destination

    @contextmanager
    def materialized(*_):
        yield Mock(path=str(tmp_path / 'frozen-work.db'))

    def generated(*args):
        directory = tmp_path / 'frozen-work.generated'
        directory.mkdir(exist_ok=True)
        file_id = 'generated-asset'
        (directory / (file_id + ('.pdf' if output == 'pdf' else '.pptx'))).write_bytes(b'output')
        (directory / (file_id + '.json')).write_text(
            json.dumps({'unresolved': [], 'fields': {}}))
        return {'file_id': file_id, 'slide_count': 2 if output == 'pdf' else 3}

    def rendered(path, kind, result):
        if kind == 'pdf':
            return path, {'rendered': True, 'actual_playback_verified': False}
        preview = path.with_suffix('.preview.pdf')
        preview.write_bytes(b'preview')
        return preview, {'rendered': True, 'actual_playback_verified': False}

    records = []
    def upload(*args, **kwargs):
        records.append({'path': args[1], 'folder': args[2], 'name': args[3]})
        return {'file_id': 'uploaded-id', 'filename': args[3]}

    with (
        patch('media_automation.cloud.worker.materialize', materialized),
        patch('media_automation.web.original.generation.generate', generated),
        patch('media_automation.web.original.bulletin_generation.generate_bulletin', generated),
        patch('media_automation.cloud.worker.upload_verified', upload),
    ):
        result = execute(identifier, 'execution-1', backend, cloud, render=rendered)

    assert result['succeeded']
    cloud.archive_destination.assert_called_once_with(service, output)
    assert len(records) == (2 if output == 'pdf' else 3)
    assert all(row['folder'] is destination for row in records)
    assert all(row['name'].startswith(snapshot['day'] + '-' + service + '-')
               for row in records)
    assert records[0]['name'].endswith('.pdf' if output == 'pdf' else '.pptx')
    assert records[-1]['name'].endswith('.report.json')
    assert backend.finish.call_args.args[2] is True
