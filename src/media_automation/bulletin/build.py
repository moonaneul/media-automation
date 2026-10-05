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
    merge_result = (
        merge_bulletin_transfer(
            sunday,
            transfer,
        )
    )

    document = build_bulletin_document(
        merge_result.sunday
    )

    pdf_result = render_bulletin_pdf(
        document,
        output_pdf,
    )

    return BulletinBuildResult(
        merge=merge_result,
        pdf=pdf_result,
    )
