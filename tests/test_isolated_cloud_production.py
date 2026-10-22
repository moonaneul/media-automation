"""Offline staged production safety checks. Uses only synthetic inputs and tmp_path.

No live Supabase account, Secret Manager, OneDrive, Google Cloud Run or
actual church originals are accessed by any test in this module.
"""
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest

from media_automation.cloud.worker import execute, render_artifact
from media_automation.web.original.work_store import RevisionConflict, WorkStore


@pytest.fixture(autouse=True)
def block_all_outbound_network(monkeypatch):
    """A regression must never turn this fixture into a live cloud test."""
    def deny(*_args, **_kwargs):
        raise AssertionError("Unexpected network access in offline production safety tests")
    monkeypatch.setattr(socket.socket, "connect", deny)
    monkeypatch.setattr(socket.socket, "connect_ex", deny)


class FrozenBackend:
    """Simulates a single-use queue claim and a monotonic cancellation check."""
    def __init__(self, identifier, service, output, active=True):
        self.identifier = identifier
        self.claimed = False
        self.active = active
        self.finish_calls = []
        self.fail_final_ack = False
        self.payload = {
            "claimed": True, "id": identifier, "output": output,
            "snapshot": {
                "day": "2026-10-21", "service": service, "catalog_revision": 4,
                "work": {"revision": 2, "data": {
                    "fields": {
                        "성경 본문": {"state": "VALUE", "value": "시 1:1"},
                        "설교 제목": {"state": "VALUE", "value": "격리 테스트"}
                    }
                }}
            }, "groups": []
        }

    def claim(self, identifier, execution):
        assert identifier == self.identifier
        if self.claimed:
            return {"claimed": False}
        self.claimed = True
        return self.payload

    def call(self, name, body):
        assert name == "media_job_active"
        assert body["p_id"] == self.identifier
        return {"active": self.active}

    def finish(self, identifier, execution, success, result):
        assert identifier == self.identifier
        self.finish_calls.append((success, result))
        if self.fail_final_ack:
            return {"finished": False}
        return {"finished": True}


def run_synthetic_worker(tmp_path, *, service="wednesday", output="ppt", fault=None):
    identifier = str(uuid4())
    backend = FrozenBackend(identifier, service, output, active=fault != "cancel-before-start")
    cloud = SimpleNamespace(archive_destination=lambda svc, fmt: {"id": "isolated-" + svc + "-" + fmt})
    uploaded = []
    attempted = []
    produced = []

    # This preexisting approved output must remain untouched on ANY failure.
    existing = tmp_path / "previous-approved-output.pptx"
    existing.write_bytes(b"PREVIOUS_APPROVED_OUTPUT")

    @contextmanager
    def fake_materialize(snapshot, cloud_obj, fmt):
        assert snapshot is backend.payload["snapshot"]
        assert cloud_obj is cloud and fmt == output
        yield SimpleNamespace(path=str(tmp_path / "frozen-work.db"))

    def fake_generate(store, body):
        assert store.path.endswith("frozen-work.db")
        assert body["revision"] == 2
        assert body["groups"] == []
        assert body["service"] == service and body["output"] == output
        produced.append(body)
        if fault == "generation":
            raise ValueError("synthetic generation interruption")
        directory = Path(store.path).with_suffix(".generated")
        directory.mkdir(exist_ok=True)
        file_id = "f" * 32
        path = directory / (file_id + (".pdf" if output == "pdf" else ".pptx"))
        path.write_bytes(b"SYNTHETIC_ARTIFACT_ONLY")
        (directory / (file_id + ".json")).write_text(
            json.dumps({"unresolved": [], "fields": {}}, ensure_ascii=False),
            encoding="utf-8"
        )
        return {"file_id": file_id, "slide_count": 2 if output == "pdf" else 4}

    def fake_render(path, fmt, result):
        assert path.is_file() and result["file_id"] == "f" * 32
        if fault == "render":
            raise ValueError("synthetic render interruption")
        if fmt == "pdf":
            return path, {"rendered": True, "visual_review_pending": True}
        pdf = path.with_suffix(".preview.pdf")
        pdf.write_bytes(b"SYNTHETIC_PREVIEW_ONLY")
        return pdf, {"rendered": True, "visual_review_pending": True}

    def fake_upload(cloud_obj, path, folder, name, checkpoint):
        checkpoint()
        assert cloud_obj is cloud
        assert folder == {"id": "isolated-" + service + "-" + output}
        assert name.startswith("2026-10-21-" + service + "-" + identifier.replace("-", ""))
        assert path.exists() and path.stat().st_size > 0
        attempted.append(name)
        if fault == "upload-" + str(len(attempted)):
            raise OSError("synthetic upload interruption")
        uploaded.append(name)
        return {"filename": name, "item_id": "fake-id-" + str(len(uploaded)),
                "drive_id": "isolated-synthetic", "size": path.stat().st_size,
                "digest": "0" * 64}

    if fault == "finish":
        backend.fail_final_ack = True
    with (
        patch("media_automation.cloud.worker.materialize", fake_materialize),
        patch("media_automation.web.original.generation.generate", fake_generate),
        patch("media_automation.web.original.bulletin_generation.generate_bulletin", fake_generate),
        patch("media_automation.cloud.worker.upload_verified", fake_upload),
    ):
        result = execute(identifier, "offline-execution", backend, cloud, render=fake_render)
        if fault == "duplicate":
            second = execute(identifier, "offline-execution", backend, cloud, render=fake_render)
            assert second == {"claimed": False}
    assert existing.read_bytes() == b"PREVIOUS_APPROVED_OUTPUT"
    return result, backend, uploaded, attempted, produced


@pytest.mark.parametrize("service,output", [
    ("wednesday", "ppt"), ("friday", "ppt"),
    ("sunday", "ppt"), ("sunday", "pdf")
])
def test_isolated_full_worker_handoff_archives_all_parts_unapproved(tmp_path, service, output):
    result, backend, files, attempted, produced = run_synthetic_worker(
        tmp_path, service=service, output=output
    )
    assert result["succeeded"] is True
    assert len(produced) == 1
    assert len(files) == (2 if output == "pdf" else 3)
    assert files == attempted
    assert files[0].endswith(".pdf" if output == "pdf" else ".pptx")
    assert files[-1].endswith(".report.json")
    successful, payload = backend.finish_calls[0]
    assert successful is True
    assert payload["complete"] is False
    assert payload["visual_review_pending"] is True
    assert payload["verification"]["visual_review_pending"] is True


@pytest.mark.parametrize("fault,stage,uploaded_parts", [
    ("cancel-before-start", "snapshot", 0),
    ("generation", "generation", 0),
    ("render", "render", 0),
    ("upload-1", "upload", 0),
    ("upload-2", "upload", 1),
    ("upload-3", "upload", 2),
])
def test_fault_injection_never_approves_existing_output(tmp_path, fault, stage, uploaded_parts):
    result, backend, files, attempted, _ = run_synthetic_worker(tmp_path, fault=fault)
    assert result == {"claimed": True, "succeeded": False, "stage": stage}
    assert len(files) == uploaded_parts
    assert len(attempted) == uploaded_parts + int(fault.startswith("upload-"))
    assert backend.finish_calls == [(False, {
        "error": "제작을 완료하지 못했습니다. 입력과 자료를 확인한 뒤 다시 요청하세요.",
        "stage": stage
    })]


def test_missing_finish_ack_does_not_report_success_or_replay_upload(tmp_path):
    result, backend, files, attempted, _ = run_synthetic_worker(tmp_path, fault="finish")
    assert result["succeeded"] is False and result["stage"] == "finish"
    assert len(files) == len(attempted) == 3
    # An unknown acknowledgment is NOT automatically followed by another finish
    # call or duplicate upload.
    assert len(backend.finish_calls) == 1
    assert backend.finish_calls[0][0] is True


def test_repeated_worker_claim_cannot_duplicate_archive(tmp_path):
    result, backend, files, attempted, _ = run_synthetic_worker(tmp_path, fault="duplicate")
    assert result["succeeded"] is True
    assert len(files) == len(attempted) == 3
    assert len(backend.finish_calls) == 1


@pytest.mark.parametrize("pages,landscape", [(2, True), (1, True), (2, False)])
def test_actual_pdf_render_check_uses_only_synthetic_a4(tmp_path, pages, landscape):
    import pymupdf

    path = tmp_path / "synthetic-bulletin.pdf"
    doc = pymupdf.open()
    for _ in range(pages):
        if landscape:
            doc.new_page(width=841.89, height=595.28)
        else:
            doc.new_page(width=595.28, height=841.89)
    doc.save(str(path))
    doc.close()

    if pages == 2 and landscape:
        result_path, verification = render_artifact(path, "pdf", {"slide_count": 0})
        assert result_path == path
        assert verification["page_count"] == 2
        assert verification["rendered"] is True
        assert verification["visual_review_pending"] is True
        assert verification["actual_playback_verified"] is False
    else:
        with pytest.raises(ValueError):
            render_artifact(path, "pdf", {"slide_count": 0})


def _draft(label):
    return {"fields": {"설교 제목": {"state": "VALUE", "value": label}}}


def test_two_offline_clients_competing_on_same_week_preserve_winner(tmp_path):
    """SQLite local CAS models the same revision conflict visible in the UI."""
    db_path = tmp_path / "isolated-shared.sqlite"
    first, second = WorkStore(db_path), WorkStore(db_path)
    before = first.save("2026-10-21", "wednesday", 0, _draft("original"))
    assert before["revision"] == 1
    barrier = Barrier(2)

    def save_from_editor(store, text):
        observed = store.get("2026-10-21", "wednesday")["revision"]
        barrier.wait(timeout=5)
        try:
            stored = store.save("2026-10-21", "wednesday", observed, _draft(text))
            return ("saved", stored)
        except RevisionConflict as error:
            return ("conflict", error.current)

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(save_from_editor, first, "device-A")
        b = pool.submit(save_from_editor, second, "device-B")
        results = [a.result(timeout=10), b.result(timeout=10)]

    assert sorted(item[0] for item in results) == ["conflict", "saved"]
    winner = first.get("2026-10-21", "wednesday")
    assert winner["revision"] == 2
    assert winner["data"]["fields"]["설교 제목"]["value"] in ("device-A", "device-B")
    loser = next(v for kind, v in results if kind == "conflict")
    assert loser == winner

    # A different service must never be overwritten by a concurrent edit.
    untouched = second.save("2026-10-23", "friday", 0, _draft("other service"))
    assert untouched["revision"] == 1
    assert first.get("2026-10-23", "friday")["data"] == _draft("other service")
