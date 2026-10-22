"""Synthetic Supabase RPC tests for concurrent editors and uncertain saves.

The HTTP transport is always mocked; no Supabase project or login is contacted.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
from threading import Barrier, Lock

import pytest
import requests

from media_automation.cloud.supabase_work_store import (
    SupabaseWorkStore, WorkStoreUnavailable,
)
from media_automation.web.original.work_store import RevisionConflict


def _data(title):
    return {"fields": {"설교 제목": {"state": "VALUE", "value": title}}}


class _Response:
    status_code = 200

    def __init__(self, data):
        self.value = deepcopy(data)

    def json(self):
        return deepcopy(self.value)


class FakeSupabaseRPC:
    """The mock performs revision CAS atomically to check client handling."""
    def __init__(self):
        self.lock = Lock()
        self.rows = {}
        self.save_calls = 0
        self.raise_after_commit = False

    def request(self, method, url, headers, json=None, **kwargs):
        assert kwargs["allow_redirects"] is False
        assert "timeout" in kwargs
        assert url.startswith("https://fake-test.supabase.co/rest/v1/rpc/")
        assert headers["apikey"] == "sb_publishable_test_fixture"
        assert headers["Authorization"] in ("Bearer editor-A", "Bearer editor-B")
        assert method == "POST" and isinstance(json, dict)
        assert not any("secret" in value.lower() for value in headers.values())
        day, service = json["p_day"], json["p_service"]
        key = (day, service)
        with self.lock:
            record = self.rows.get(key, {"revision": 0, "data": {}, "updated_at": None})
            operation = url.rsplit("/", 1)[-1]
            if operation == "media_get_work":
                return _Response(record)
            assert operation == "media_save_work"
            self.save_calls += 1
            if json["p_expected_revision"] != record["revision"]:
                return _Response({"saved": False, "current": record})
            next_record = {
                "revision": record["revision"] + 1,
                "data": deepcopy(json["p_data"]),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.rows[key] = next_record
            if self.raise_after_commit:
                self.raise_after_commit = False
                raise requests.Timeout("simulated reply lost after a successful commit")
            return _Response({"saved": True, "current": next_record})


@pytest.fixture
def transport(monkeypatch):
    fake = FakeSupabaseRPC()
    monkeypatch.setattr(
        "media_automation.cloud.supabase_work_store.requests.request",
        fake.request
    )
    return fake


def _client(label):
    return SupabaseWorkStore(
        "https://fake-test.supabase.co",
        "sb_publishable_test_fixture",
        "editor-" + label,
    )


def test_two_cloud_editor_clients_cannot_silently_overwrite_the_same_revision(transport):
    a, b = _client("A"), _client("B")
    date, service = "2026-10-25", "sunday"
    assert a.get(date, service)["revision"] == 0
    both_read = Barrier(2)

    def edit(client, title):
        baseline = client.get(date, service)["revision"]
        both_read.wait(timeout=5)
        try:
            return ("saved", client.save(date, service, baseline, _data(title)))
        except RevisionConflict as err:
            return ("conflict", err.current)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa, fb = pool.submit(edit, a, "device-A"), pool.submit(edit, b, "device-B")
        results = [fa.result(timeout=10), fb.result(timeout=10)]

    assert sorted(k for k, _ in results) == ["conflict", "saved"]
    current = a.get(date, service)
    assert current["revision"] == 1
    assert current["data"]["fields"]["설교 제목"]["value"] in ("device-A", "device-B")
    assert current == b.get(date, service)
    assert next(v for kind, v in results if kind == "conflict") == current
    assert transport.save_calls == 2


def test_ack_lost_after_server_save_requires_reload_not_blind_retry(transport):
    a, b = _client("A"), _client("B")
    date, service = "2026-10-21", "wednesday"
    transport.raise_after_commit = True
    with pytest.raises(WorkStoreUnavailable, match="다시 불러와 확인하세요"):
        a.save(date, service, 0, _data("confirmed-but-reply-lost"))
    assert transport.save_calls == 1
    current = b.get(date, service)
    assert current["revision"] == 1
    assert current["data"] == _data("confirmed-but-reply-lost")
    with pytest.raises(RevisionConflict):
        a.save(date, service, 0, _data("stale-blind-retry"))
    assert b.get(date, service)["data"] == _data("confirmed-but-reply-lost")


def test_unset_or_explicitly_absent_values_remain_distinct(transport):
    a, b = _client("A"), _client("B")
    date, service = "2026-10-23", "friday"
    original = {
        "fields": {
            "기도 담당자": {"state": "NONE", "value": ""},
            "설교 제목": {"state": "UNSET", "value": ""},
            "성경 본문": {"state": "VALUE", "value": "시 1:1"},
        }
    }
    saved = a.save(date, service, 0, original)
    assert saved["revision"] == 1
    assert b.get(date, service)["data"] == original
    assert transport.save_calls == 1
