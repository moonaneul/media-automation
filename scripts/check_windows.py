from __future__ import annotations

import platform
import sys


def main() -> None:
    print("Python:", sys.version)
    print("Platform:", platform.platform())

    if platform.system() != "Windows":
        raise SystemExit(
            "이 검사는 Windows에서 실행해야 합니다."
        )

    try:
        import win32com.client
    except ImportError as exc:
        raise SystemExit(
            "pywin32가 설치되지 않았습니다."
        ) from exc

    print("pywin32: OK")

    powerpoint = None

    try:
        powerpoint = (
            win32com.client.DispatchEx(
                "PowerPoint.Application"
            )
        )

        print(
            "PowerPoint COM: OK"
        )
        print(
            "PowerPoint version:",
            powerpoint.Version,
        )

    except Exception as exc:
        raise SystemExit(
            "PowerPoint COM 연결 실패: "
            f"{exc}"
        ) from exc

    finally:
        if powerpoint is not None:
            try:
                powerpoint.Quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
