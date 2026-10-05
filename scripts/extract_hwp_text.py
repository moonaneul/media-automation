from __future__ import annotations

import argparse
from pathlib import Path

from media_automation.bulletin.hwp import (
    extract_hwp_text,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "input",
        help="입력 HWP 파일",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="출력 UTF-8 TXT 파일",
    )

    args = parser.parse_args()

    text = extract_hwp_text(
        args.input
    )

    output = Path(args.output)

    output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output.write_text(
        text,
        encoding="utf-8",
    )

    print("추출 완료:", output)
    print("문자 수:", len(text))


if __name__ == "__main__":
    main()
