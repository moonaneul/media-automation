import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location('uploader', Path(__file__).resolve().parents[1] / 'scripts/upload_missing_sources.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def fake(path, content):
    path.write_bytes(content)
    digest = hashlib.sha256(content).hexdigest()
    item = {'id': 'item', 'size': len(content), 'file': {}}
    cloud = Mock()
    cloud.children.return_value = []
    cloud.graph.return_value = {'uploadUrl': 'https://files.1drv.com/upload'}
    cloud.http.put.return_value = Mock(status_code=201, json=Mock(return_value=item))
    cloud.within.return_value = True
    cloud.item.return_value = item
    cloud._download.return_value = content
    return cloud, digest


def test_new_upload_never_requests_replacement_and_verifies_download_hash(tmp_path):
    p = tmp_path / 'original'; cloud, digest = fake(p, b'original bytes')
    item, created = module.upload_new(cloud, {'id': 'source'}, p, '곡.ppt', digest)
    assert created and item['id'] == 'item'
    assert cloud.graph.call_args.kwargs['body']['item']['@microsoft.graph.conflictBehavior'] == 'fail'
    assert 'Authorization' not in cloud.http.put.call_args.kwargs['headers']
    assert cloud._download.call_count == 1


def test_existing_name_with_different_content_is_never_overwritten(tmp_path):
    p = tmp_path / 'original'; cloud, digest = fake(p, b'original bytes')
    cloud.children.return_value = [{'name': '곡_' + digest + '.ppt', 'id': 'existing', 'size': p.stat().st_size}]
    cloud._download.return_value = b'wrong contents'
    with pytest.raises(module.CloudError):
        module.upload_new(cloud, {'id': 'source'}, p, '곡.ppt', digest)
    cloud.graph.assert_not_called(); cloud.http.put.assert_not_called()


def test_local_hash_mismatch_stops_before_network_write(tmp_path):
    p = tmp_path / 'original'; cloud, _ = fake(p, b'original bytes')
    with pytest.raises(ValueError):
        module.upload_new(cloud, {'id': 'source'}, p, '곡.ppt', 'a' * 64)
    cloud.graph.assert_not_called(); cloud.http.put.assert_not_called()


def test_upload_url_cannot_send_original_to_untrusted_host(tmp_path):
    p = tmp_path / 'original'; cloud, digest = fake(p, b'original bytes')
    cloud.graph.return_value = {'uploadUrl': 'https://untrusted.example/upload'}
    with pytest.raises(module.CloudError):
        module.upload_new(cloud, {'id': 'source'}, p, '곡.ppt', digest)
    cloud.http.put.assert_not_called()
