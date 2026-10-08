from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from media_automation.bulletin.document import (
    build_bulletin_document,
)
from media_automation.bulletin.hwp import (
    extract_hwp_text,
)
from media_automation.bulletin.merge import (
    BulletinMergeResult,
    merge_bulletin_transfer,
)
from media_automation.bulletin.pdf import (
    BulletinPdfResult,
    render_bulletin_pdf,
)
from media_automation.bulletin.transfer import (
    parse_bulletin_transfer_text,
)
from media_automation.weekly_data.loader import (
    load_yaml,
)
from media_automation.weekly_data.models import (
    SundayData,
    WeeklyStatus,
)


def _load_transfer_source(
    path: str | Path,
) -> str:
    source = Path(path)

    if not source.exists():
        raise FileNotFoundError(
            "전달 주보 파일을 찾을 수 없습니다: "
            f"{source}"
        )

    if source.suffix.lower() in {
        ".hwp",
        ".hwpx",
    }:
        return extract_hwp_text(
            source
        )

    return source.read_text(
        encoding="utf-8"
    )


@dataclass(frozen=True, slots=True)
class BulletinBuildResult:
    merge: BulletinMergeResult
    pdf: BulletinPdfResult


def build_bulletin_from_files(
    *,
    sunday_yaml: str | Path,
    output_pdf: str | Path,
    transfer_source: str | Path | None = None,
    transfer_text: str | Path | None = None,
    already_merged: bool = False,
    design: str = "classic",
) -> BulletinBuildResult:
    sunday_path = Path(sunday_yaml)

    if not sunday_path.exists():
        raise FileNotFoundError(
            f"주일예배 YAML을 찾을 수 없습니다: "
            f"{sunday_path}"
        )

    if (
        transfer_source is not None
        and transfer_text is not None
    ):
        raise ValueError(
            "transfer_source와 transfer_text를 "
            "동시에 지정할 수 없습니다."
        )

    source = (
        transfer_source
        if transfer_source is not None
        else transfer_text
    )

    if source is None:
        raise ValueError(
            "전달 주보 입력 파일이 필요합니다."
        )

    # 같은 주 주일예배 안내
    raw_sunday = load_yaml(
        sunday_path
    )

    sunday = SundayData.model_validate(
        raw_sunday
    )

    number = sunday.bulletin.number
    if number.status != WeeklyStatus.VALUE or not (number.value or "").strip():
        raise ValueError(
            "주보 호수가 없습니다. 해당 주에 확인된 호수를 등록한 "
            "주보용 데이터를 사용해주세요."
        )

    # 전달 HWP에서 추출한 텍스트
    transfer_raw = (
        _load_transfer_source(
            source
        )
    )

    transfer = (
        parse_bulletin_transfer_text(
            transfer_raw,
            year=sunday.date.year,
        )
    )

    # 날짜 불일치 등은 여기서 즉시 실패
    if already_merged:
        if sunday.date != transfer.date:
            raise ValueError(
                f"주일 데이터와 전달 주보 날짜가 다릅니다: {sunday.date} != {transfer.date}"
            )
        merge_result = BulletinMergeResult(sunday=sunday, praise_raw=transfer.praise_raw)
    else:
        merge_result = merge_bulletin_transfer(sunday, transfer)

    document = build_bulletin_document(
        merge_result.sunday
    )

    if design == "modern":
        from reportlab.lib.pagesizes import A4, landscape
        from media_automation.bulletin.modern import render_modern_bulletin
        from media_automation.bulletin.pdf import build_imposition_plan
        photo = Path(__file__).resolve().parents[3] / "assets/bulletin/autumn_soft_v2.png"
        if not photo.is_file():
            raise FileNotFoundError(f"확정된 주보 표지 사진이 없습니다: {photo}")
        path = render_modern_bulletin(document, output_pdf, photo)
        width, height = landscape(A4)
        pdf_result = BulletinPdfResult(path=path, sheets=build_imposition_plan(),
                                      width=width, height=height)
    elif design == "classic":
        pdf_result = render_bulletin_pdf(document, output_pdf)
    else:
        raise ValueError(f"지원하지 않는 주보 디자인입니다: {design}")

    return BulletinBuildResult(
        merge=merge_result,
        pdf=pdf_result,
    )
