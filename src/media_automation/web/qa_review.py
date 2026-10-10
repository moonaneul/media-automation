"""Persistent, artifact-bound inspection and human review for local jobs.

Only files from a generated job's artifact allowlist may enter these helpers.
Records live outside the production workspace and never modify the artifact.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from media_automation.qa.inspection import inspect_file

_CHECK_LABELS = {
    "visual": "실제 렌더링 화면과 글씨/악보 잘림 확인",
    "powerpoint_open": "PowerPoint에서 복구 경고 없이 열림",
    "playback": "미디어가 실제 예배 환경에서 재생되는지 확인",
    "rights": "악보·영상·이미지 사용 허락 확인",
    "printing": "양면 출력 및 가운데 접지 실물 확인",
}
_STATES = {"pending", "checked", "issue"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record_path(job_dir: Path, relative: str) -> Path:
    token = hashlib.sha256(relative.encode("utf-8")).hexdigest()
    return job_dir / "qa" / (token + ".json")


def _required(service: str, automatic: dict) -> dict[str, str]:
    if service == "bulletin":
        keys = ("visual", "printing", "rights")
    else:
        keys = ["visual", "powerpoint_open", "rights"]
        if automatic.get("stats", {}).get("media_relationships", 0):
            keys.append("playback")
    return {key: _CHECK_LABELS[key] for key in keys}


def _load(job_dir: Path, relative: str) -> dict | None:
    path = _record_path(job_dir, relative)
    if not path.is_file():
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("artifact") != relative:
        raise ValueError("검수 기록 형식 또는 파일 연결이 올바르지 않습니다.")
    return value


def _save(job_dir: Path, relative: str, data: dict) -> None:
    destination = _record_path(job_dir, relative)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def inspect(job_dir: Path, relative: str, artifact: Path, service: str,
            reference: str | None = None) -> dict:
    """Explicit inspection; restarting inspection invalidates past human checks."""
    if reference is not None:
        if not isinstance(reference, str) or len(reference) > 80:
            raise ValueError("성경 본문 범위는 80자 이내의 문자열이어야 합니다.")
        reference = reference.strip() or None
    automatic = inspect_file(
        artifact,
        service="friday_zoom" if service == "friday" else service,
        expected_reference=reference,
    )
    # Never save the operator's absolute home path in downloadable reports.
    automatic["file"] = relative
    automatic["reference_requested"] = reference
    record = {
        "schema_version": 1,
        "artifact": relative,
        "sha256": _sha256(artifact),
        "inspected_at": _now(),
        "automatic": automatic,
        "human": {
            "reviewer": None, "note": "",
            "updated_at": None, "checks": {},
        },
    }
    _save(job_dir, relative, record)
    return status(job_dir, relative, artifact, service)


def status(job_dir: Path, relative: str, artifact: Path, service: str) -> dict:
    record = _load(job_dir, relative)
    if record is None:
        return {"available": False, "stale": False, "artifact": relative,
                "message": "아직 이 산출물에 대해 자동 검수를 실행하지 않았습니다."}
    if record.get("sha256") != _sha256(artifact):
        return {"available": False, "stale": True, "artifact": relative,
                "message": "산출물 내용이 변경되었습니다. 이전 검수 기록은 무효입니다. 다시 검사해주세요."}
    result = dict(record)
    result.update(available=True, stale=False)
    labels = _required(service, record["automatic"])
    human = result["human"]
    checks = dict(human.get("checks") or {})
    human["checks"] = {key: checks.get(key, "pending") for key in labels}
    result["check_labels"] = labels
    summary = record["automatic"].get("summary", {})
    human_complete = bool(human.get("reviewer")) and all(
        value == "checked" for value in human["checks"].values()
    )
    result["human_review_complete"] = human_complete
    # A structural error cannot be cleared by a human checkbox.
    result["review_record_complete"] = human_complete and summary.get("error", 0) == 0
    return result


def confirm(job_dir: Path, relative: str, artifact: Path, service: str,
            payload: dict) -> dict:
    current = status(job_dir, relative, artifact, service)
    if not current["available"]:
        raise ValueError("해당 산출물에 유효한 검수 기록이 없습니다. 먼저 자동 검사해주세요.")
    if payload.get("sha256") != current["sha256"]:
        raise ValueError("파일이 바뀌었거나 이전 검수 화면입니다. 다시 불러와주세요.")
    reviewer = payload.get("reviewer")
    note = payload.get("note", "")
    supplied = payload.get("checks")
    if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 80:
        raise ValueError("검수자 이름을 1~80자로 입력해주세요.")
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError("검수 메모는 2000자 이내로 입력해주세요.")
    labels = current["check_labels"]
    if not isinstance(supplied, dict) or set(supplied) != set(labels):
        raise ValueError("해당 산출물의 확인 항목을 모두 전달해주세요.")
    if any(value not in _STATES for value in supplied.values()):
        raise ValueError("검수 상태는 미확인/확인 완료/문제 발견 중에서 선택해주세요.")
    record = _load(job_dir, relative)
    record["human"] = {
        "reviewer": reviewer.strip(),
        "note": note.strip(),
        "updated_at": _now(),
        "checks": {key: supplied[key] for key in labels},
    }
    _save(job_dir, relative, record)
    return status(job_dir, relative, artifact, service)


def report_bytes(job_dir: Path, relative: str, artifact: Path, service: str) -> bytes:
    current = status(job_dir, relative, artifact, service)
    if not current["available"]:
        raise ValueError("유효한 검수 보고서가 없습니다.")
    return (json.dumps(current, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
