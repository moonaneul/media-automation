"""Read-only, week-scoped work dashboard. No new storage or auto-approval."""
from __future__ import annotations

from datetime import date, timedelta

SLOTS = (
    ("wednesday", 2, "수요예배"),
    ("friday", 4, "금요기도회 Zoom"),
    ("sunday", 6, "주일예배"),
    ("bulletin", 6, "주일 주보"),
)
_STATES = {
    "needs_input": "자료 준비 중",
    "queued": "제작 대기",
    "running": "제작 중",
    "generated": "제작 파일 있음 · 최종 검수 별도",
    "failed": "제작 실패",
    "interrupted": "중단됨 · 새 작업 필요",
}


def build_dashboard(jobs: list[dict], day: str) -> dict:
    """Group only explicitly created local jobs for a Monday–Sunday week."""
    selected = date.fromisoformat(day)
    week_start = selected - timedelta(days=selected.weekday())
    buckets: dict[str, list[dict]] = {service: [] for service, _, _ in SLOTS}
    dates = {service: (week_start + timedelta(days=offset)).isoformat()
             for service, offset, _ in SLOTS}
    for job in jobs:
        service = job.get("service")
        if service not in buckets or job.get("date") != dates[service]:
            continue
        has_artifact = job["state"] == "generated" and bool(job.get("artifacts"))
        status = ("결과 파일 확인 필요" if job["state"] == "generated" and not has_artifact
                  else _STATES.get(job["state"], "상태 확인 필요"))
        buckets[service].append({
            "job_id": job["job_id"],
            "state": job["state"],
            "status": status,
            "created_at": job["created_at"],
            "has_artifact": has_artifact,
        })
    slots = []
    for service, _, label in SLOTS:
        ordered = sorted(buckets[service],
                         key=lambda row: (row["created_at"], row["job_id"]), reverse=True)
        slots.append({
            "service": service, "label": label, "date": dates[service],
            "latest": ordered[0] if ordered else None,
            "latest_generated": next((row for row in ordered if row["has_artifact"]), None),
            "jobs": ordered,
            "status": ordered[0]["status"] if ordered else "아직 작업 없음",
            "has_multiple": len(ordered) > 1,
        })
    return {
        "week_start": week_start.isoformat(),
        "week_end": (week_start + timedelta(days=6)).isoformat(),
        "slots": slots,
        "note": "상태는 이 로컬 저장소에 등록된 작업 기준입니다. 생성 완료는 최종 검수 완료가 아닙니다.",
    }
