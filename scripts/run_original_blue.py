"""Run original blue UI together with its original APIs on loopback only.

It is an isolated recovery runner, not the canonical production web server.
Never reads / modifies existing worship material or browser storage on another port.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description="원래 파란색 웹사이트 복구 실행기 (로컬 전용)")
    parser.add_argument("--port", type=int, default=18767)
    parser.add_argument(
        "--database",
        type=Path,
        default=Path.home() / "Documents/media-automation-integration/original-blue-working/work.sqlite",
    )
    args = parser.parse_args()
    if not (1 <= args.port <= 65535):
        parser.error("포트는 1~65535 사이여야 합니다.")

    backend = Path(__file__).resolve().parents[1] / "src/media_automation/_legacy_migration/backend"
    if not (backend / "server.py").is_file():
        parser.error("원본 웹 서버 파일이 없습니다.")
    sys.path.insert(0, str(backend))
    from server import make_server
    from work_store import WorkStore

    database = args.database.expanduser().resolve()
    database.parent.mkdir(parents=True, exist_ok=True)
    import os
    password = os.environ.get("MEDIA_ACCESS_PASSWORD") or None
    server = make_server(WorkStore(database), args.port, password, "127.0.0.1")
    print("원본 파란색 웹사이트: http://127.0.0.1:%d/" % server.server_port, flush=True)
    print("저장 위치: %s" % database, flush=True)
    print("로컬 복구 시험판입니다. PPT/PDF 실제 제작 기능은 별도 검증이 필요합니다.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
