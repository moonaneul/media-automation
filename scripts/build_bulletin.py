from __future__ import annotations

import argparse

from media_automation.bulletin.build import (
    build_bulletin_from_files,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "같은 주 Sunday YAML과 "
            "전달 주보 추출 텍스트를 병합하여 "
            "인쇄용 주보 PDF를 생성합니다."
        )
    )

    parser.add_argument(
        "--sunday",
        required=True,
        help="같은 주 SundayData YAML",
    )

    transfer_group = (
        parser.add_mutually_exclusive_group(
            required=True
        )
    )

    transfer_group.add_argument(
        "--transfer",
        help=(
            "전달 주보 원본 .hwp/.hwpx "
            "또는 UTF-8 TXT"
        ),
    )

    transfer_group.add_argument(
        "--transfer-text",
        help=(
            "기존 호환용: HWP에서 추출한 "
            "UTF-8 텍스트 파일"
        ),
    )

    parser.add_argument(
        "--output",
        required=True,
        help="생성할 PDF 경로",
    )

    args = parser.parse_args()

    result = build_bulletin_from_files(
        sunday_yaml=args.sunday,
        transfer_source=(
            args.transfer
            if args.transfer is not None
            else args.transfer_text
        ),
        output_pdf=args.output,
    )

    print(
        "주보 PDF 생성 완료:",
        result.pdf.path,
    )

    if (
        result.merge.praise_raw.value
        is not None
    ):
        print(
            "전달 주보 찬양 원문:",
            result.merge.praise_raw.value,
        )
        print(
            "※ 찬양 역할은 임의 매핑하지 "
            "않았습니다."
        )


if __name__ == "__main__":
    main()
