"""Offline Microsoft Graph transfer-contract checks using synthetic, in-memory data.

No Microsoft account, OneDrive, Supabase, GCP credentials or network are used.
These tests exercise the real upload_verified/download_verified functions.
"""
import hashlib
import socket
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import unquote

import pytest
import requests

from media_automation.cloud.artifacts import download_verified, upload_verified
from media_automation.web.original.onedrive import CloudError


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def blocked(*_args, **_kwargs):
        raise AssertionError("Network is forbidden in synthetic OneDrive tests")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", blocked)


class FakeResponse:
    def __init__(self, status, *, value=None, data=b""):
        self.status_code, self._value, self._data = status, value, data

    def json(self):
        return self._value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def iter_content(self, chunk_size):
        for start in range(0, len(self._data), chunk_size):
            yield self._data[start:start + chunk_size]


class SyntheticGraphDrive:
    """Only the permitted isolated archive folder can receive new files."""
    def __init__(self):
        self.folder = {"id": "staging-folder", "parentReference": {"driveId": "test-drive"}}
        self.http = self
        self.objects = {}
        self.started = []
        self.put_count = 0
        self.get_count = 0
        self.upload_status_override = None
        self.corrupt_download = False
        self.change_download_host = False
        self.wrong_parent = False
        self.wrong_size = False
        self.session_name = None
        self.session_data = b""

    def graph(self, path, method=None, body=None):
        assert method == "POST"
        assert path.startswith("/me/drive/items/staging-folder:/")
        assert path.endswith(":/createUploadSession")
        name = unquote(path.removeprefix("/me/drive/items/staging-folder:/")
                        .removesuffix(":/createUploadSession"))
        assert body == {"item": {"@microsoft.graph.conflictBehavior": "fail", "name": name}}
        self.started.append(name)
        self.session_name = name
        self.session_data = b""
        return {"uploadUrl": "https://upload.onedrive.com/isolated-session"}

    def put(self, url, *, data, timeout, allow_redirects, headers):
        assert url == "https://upload.onedrive.com/isolated-session"
        assert timeout == (10, 120) and allow_redirects is False
        assert headers["Content-Range"].startswith("bytes ")
        self.put_count += 1
        if self.upload_status_override is not None:
            return FakeResponse(self.upload_status_override)
        if self.session_name in self.objects:
            return FakeResponse(409)  # Conflict behavior: fail, never overwrite.
        self.session_data += data
        item_id = "synthetic-item-" + str(len(self.objects) + 1)
        self.objects[self.session_name] = {
            "id": item_id, "name": self.session_name, "data": self.session_data
        }
        item = self.item(item_id)
        return FakeResponse(201, value=item)

    def get(self, url, *, stream, timeout, allow_redirects):
        assert stream is True and timeout == (10, 120) and allow_redirects is False
        assert url == "https://download.onedrive.com/isolated-item"
        self.get_count += 1
        assert len(self.objects) == 1
        payload = next(iter(self.objects.values()))["data"]
        if self.corrupt_download:
            payload = payload[:-1] + (b"X" if payload[-1:] != b"X" else b"Y")
        return FakeResponse(200, data=payload)

    def item(self, identifier):
        value = next((entry for entry in self.objects.values() if entry["id"] == identifier), None)
        assert value is not None
        return {
            "id": identifier,
            "size": len(value["data"]) + int(self.wrong_size),
            "file": {},
            "parentReference": {
                "driveId": "not-test-drive" if self.wrong_parent else "test-drive",
                "id": self.folder["id"],
            },
            "@microsoft.graph.downloadUrl": (
                "https://attacker.example/stolen" if self.change_download_host
                else "https://download.onedrive.com/isolated-item"
            )
        }

    def selected(self, purpose):
        assert purpose == "archive"
        return self.folder

    def within(self, item, folder):
        return (
            folder["id"] == self.folder["id"]
            and item["parentReference"]["id"] == folder["id"]
            and item["parentReference"]["driveId"] == folder["parentReference"]["driveId"]
        )


def _local_file(tmp_path, name="주일-검수용.pdf", data=b"FAKE PDF BYTES / NOT A CHURCH FILE"):
    path = tmp_path / name
    path.write_bytes(data)
    return path


def _stage_file(cloud, name, data):
    cloud.objects[name] = {"id": "synthetic-item-1", "name": name, "data": data}
    return {
        "item_id": "synthetic-item-1", "drive_id": "test-drive", "size": len(data),
        "filename": name, "digest": hashlib.sha256(data).hexdigest(),
    }


def test_real_transfer_functions_verify_round_trip_without_account(tmp_path):
    cloud = SyntheticGraphDrive()
    source = _local_file(tmp_path)
    record = upload_verified(cloud, source, cloud.folder, source.name)
    assert record == {
        "item_id": "synthetic-item-1", "drive_id": "test-drive",
        "size": source.stat().st_size, "filename": source.name,
        "digest": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    assert cloud.started == [source.name]
    assert cloud.put_count == 1
    assert cloud.get_count == 1  # Real function downloads after upload to verify.
    assert not list(tmp_path.glob("*.verified"))
    target = download_verified(cloud, record, tmp_path / "downloaded.pdf")
    assert target.read_bytes() == source.read_bytes()
    assert source.read_bytes() == b"FAKE PDF BYTES / NOT A CHURCH FILE"


def test_duplicate_filename_is_rejected_without_overwriting_existing_object(tmp_path):
    cloud = SyntheticGraphDrive()
    first = _local_file(tmp_path, "same.pptx", b"FIRST VERSION")
    upload_verified(cloud, first, cloud.folder, first.name)
    before = cloud.objects[first.name]["data"]
    first.write_bytes(b"SECOND VERSION")
    with pytest.raises(CloudError, match="업로드"):
        upload_verified(cloud, first, cloud.folder, first.name)
    assert cloud.objects[first.name]["data"] == before
    assert cloud.get_count == 1  # Failed second upload cannot claim verification.


@pytest.mark.parametrize("failure", ["corrupt_download", "wrong_parent", "wrong_size", "change_download_host"])
def test_verification_fails_closed_and_removes_local_temp_file(tmp_path, failure):
    cloud = SyntheticGraphDrive()
    data = b"SYNTHETIC-PDF-CONTENT-123"
    record = _stage_file(cloud, "test.pdf", data)
    setattr(cloud, failure, True)
    target = tmp_path / "partial-download.pdf"
    with pytest.raises(CloudError):
        download_verified(cloud, record, target)
    assert not target.exists()
    assert cloud.objects["test.pdf"]["data"] == data
    if failure in ("change_download_host", "wrong_parent", "wrong_size"):
        assert cloud.get_count == 0


def test_unknown_upload_status_must_not_claim_success_or_retry(tmp_path):
    cloud = SyntheticGraphDrive()
    source = _local_file(tmp_path)
    cloud.upload_status_override = 202  # A final chunk that was never completed.
    with pytest.raises(CloudError, match="업로드"):
        upload_verified(cloud, source, cloud.folder, source.name)
    assert cloud.put_count == 1
    assert cloud.get_count == 0
    assert cloud.objects == {}


def test_existing_download_is_never_replaced(tmp_path):
    cloud = SyntheticGraphDrive()
    record = _stage_file(cloud, "test.pdf", b"ISOLATED CONTENT")
    target = tmp_path / "already-approved.pdf"
    target.write_bytes(b"APPROVED CONTENT")
    with pytest.raises(FileExistsError):
        download_verified(cloud, record, target)
    assert target.read_bytes() == b"APPROVED CONTENT"
    assert cloud.get_count == 0


def test_cancellation_after_upload_does_not_mark_result_verified(tmp_path):
    cloud = SyntheticGraphDrive()
    source = _local_file(tmp_path)
    checkpoints = 0

    def checkpoint():
        nonlocal checkpoints
        checkpoints += 1
        if checkpoints == 3:
            raise RuntimeError("synthetic cancellation after transfer")

    with pytest.raises(RuntimeError, match="cancellation"):
        upload_verified(cloud, source, cloud.folder, source.name, checkpoint=checkpoint)
    assert checkpoints == 3
    assert cloud.get_count == 0
    # A remote orphan may remain. Do NOT silently delete it or claim success.
    assert cloud.objects[source.name]["data"] == source.read_bytes()
    assert source.read_bytes() == b"FAKE PDF BYTES / NOT A CHURCH FILE"


def test_untrusted_upload_session_url_is_rejected_before_http(tmp_path):
    cloud = SyntheticGraphDrive()
    source = _local_file(tmp_path)
    cloud.graph = lambda *_args, **_kwargs: {
        "uploadUrl": "https://attacker.example/capture"
    }
    with pytest.raises(CloudError, match="업로드 주소"):
        upload_verified(cloud, source, cloud.folder, source.name)
    assert cloud.put_count == cloud.get_count == 0
