from __future__ import annotations

import argparse

from media_automation.bulletin.hwp import (
    detect_hwp_format,
)


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "path",
        help="확인할 .hwp 또는 .hwpx 파일",
    )

    args = parser.parse_args()

    detected = detect_hwp_format(
        args.path
    )

    print("파일:", args.path)
    print("형식:", detected.value)


if __name__ == "__main__":
    main()
