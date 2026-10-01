import sys
from pathlib import Path

from media_automation.weekly_data import (
    ValidationState,
    validate_weekly_file,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "사용법: python scripts/validate_weekly.py "
            "<weekly-data.yaml>"
        )
        return 2

    path = Path(sys.argv[1])
    result = validate_weekly_file(path)

    print(f"[{result.state.value}] {path}")

    if result.unresolved:
        print("\n확인되지 않은 항목:")
        for item in result.unresolved:
            print(f"  - {item}")

    if result.errors:
        print("\n오류:")
        for error in result.errors:
            print(f"  - {error}")

    if result.state == ValidationState.VALID:
        return 0

    if result.state == ValidationState.INCOMPLETE:
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())