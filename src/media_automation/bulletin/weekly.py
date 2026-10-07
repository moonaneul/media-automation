from __future__ import annotations

from media_automation.bulletin.merge import merge_bulletin_transfer
from media_automation.bulletin.transfer import BulletinTransferData
from media_automation.weekly_data.models import SundayData
from media_automation.weekly_data.models import WeeklyStatus


def merge_for_sunday(
    base: SundayData,
    transfer: BulletinTransferData,
    intake: dict,
) -> SundayData:
    """Apply the transfer only where the current week's notice is silent."""
    merged = merge_bulletin_transfer(base, transfer).sunday
    fields = intake.get("fields", {})

    worship = merged.worship
    serving = merged.serving
    bulletin = merged.bulletin

    if fields.get("additional_scripture", {}).get("status") != "missing":
        worship = worship.model_copy(update={
            "additional_scripture": base.worship.additional_scripture,
        })

    second = serving.this_week.second_service
    base_second = base.serving.this_week.second_service
    if fields.get("second_service_prayer", {}).get("status") != "missing":
        second = second.model_copy(update={"prayer": base_second.prayer})
    if fields.get("second_service_offering_prayer", {}).get("status") != "missing":
        second = second.model_copy(update={
            "offering_prayer": base_second.offering_prayer,
        })
    serving = serving.model_copy(update={
        "this_week": serving.this_week.model_copy(update={
            "second_service": second,
        }),
    })

    news_record = fields.get("church_news", {})
    # "있음" only requests the PPT's church-news title slide. The transfer's
    # detailed items belong in the shared weekly data for the bulletin.
    if (
        news_record.get("status") != "missing"
        and str(news_record.get("value", "")).strip() != "있음"
    ):
        bulletin = bulletin.model_copy(update={
            "church_news": base.bulletin.church_news,
        })

    return merged.model_copy(update={
        "worship": worship,
        "serving": serving,
        "bulletin": bulletin,
    })


def alignment_differences(expected: SundayData, actual: SundayData) -> list[str]:
    """Return field paths that differ between the shared PPT/PDF weekly data."""
    differences: list[str] = []

    def walk(left, right, path: str) -> None:
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(left.keys() | right.keys()):
                walk(left.get(key), right.get(key), f"{path}.{key}" if path else key)
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append(path)
            else:
                for index, (a, b) in enumerate(zip(left, right)):
                    walk(a, b, f"{path}[{index}]")
        elif left != right:
            differences.append(path)

    walk(expected.model_dump(mode="json"), actual.model_dump(mode="json"), "")
    return differences


def sermon_crosscheck(sunday: SundayData, transfer: BulletinTransferData) -> list[str]:
    """Compare sermon references shared with the bulletin's cell-group page."""
    if transfer.cell_group.status != WeeklyStatus.VALUE:
        return []

    def normalized(value: str | None) -> str:
        return "".join((value or "").replace("-", "~").split())

    differences = []
    if (
        sunday.worship.scripture.status == WeeklyStatus.VALUE
        and normalized(sunday.worship.scripture.reference)
        != normalized(transfer.cell_group.scripture)
    ):
        differences.append("설교 본문 ↔ 목장 본문")
    if (
        sunday.worship.sermon_title.status == WeeklyStatus.VALUE
        and normalized(sunday.worship.sermon_title.text)
        != normalized(transfer.cell_group.title)
    ):
        differences.append("설교 제목 ↔ 목장 제목")
    return differences
