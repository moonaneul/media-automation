"""Test existing OneDrive archive folder upload without completing a worship output.

Explicit --execute is required; default mode only verifies local configuration.
Test files are never deleted automatically. No credentials or token are printed.
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

from media_automation.web.original.onedrive import OneDrive, CloudError


def run(database: Path, execute: bool = False, sizes: str = "both") -> int:
    if not database.is_file():
        print("ERROR: 검수 DB 파일을 찾지 못했습니다. 경로를 확인하세요.")
        return 2
    cloud = OneDrive(SimpleNamespace(path=str(database)))
    try:
        status = cloud.status("http://localhost:18877")
        if not status["connected"]:
            raise CloudError("OneDrive가 연결되지 않았습니다. 설정 화면에서 연결하세요.")
        folder = cloud.selected("archive")
        if "id" not in folder:
            raise CloudError("선택한 완료본 최상위 폴더에 ID가 없습니다.")
        # Inspect the selected folder, not the whole OneDrive.
        remote = cloud.item(folder["id"])
        if "folder" not in remote:
            raise CloudError("기존에 선택한 완료본 폴더가 이동되었거나 파일로 변경됐습니다.")
        print("대상: 기존 OneDrive 완료본 최상위 폴더")
        print("현재 설정: 연결됨 / 폴더 접근 가능")
        if not execute:
            print("읽기 전용 사전 확인 완료. 실제 업로드는 실행하지 않았습니다.")
            print("실제 시험은 --execute 를 추가하세요. 루트 폴더에 시험 파일이 남습니다.")
            return 0
        requested = (("small", 128), ("large", 6 * 1024 * 1024))
        for label, size in requested:
            if sizes not in ("both", label):
                continue
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            name = f"media-automation-TEST-{label}-{stamp}-{secrets.token_hex(6)}.bin"
            # Use new random bytes and unique filenames; never overwrite existing files.
            content = b"media-automation archive upload diagnostic\n"
            content += secrets.token_bytes(max(0, size-len(content)))
            print(f"{label}: 업로드 시작 ({len(content)} bytes)")
            try:
                item = cloud.upload_file(folder["id"], name, content)
                if not item.get("id") or item.get("name") != name or item.get("size") != len(content):
                    raise CloudError("업로드 응답의 ID/이름/크기가 예상과 다릅니다.")
                print(f"{label}: 업로드 응답 확인")
                remote_item = cloud.item(item["id"])
                if remote_item.get("id") != item["id"] or remote_item.get("size") != len(content):
                    raise CloudError("OneDrive 실제 파일 조회 결과가 예상과 다릅니다.")
                print(f"{label}: OneDrive 파일 실존 및 크기 확인")
                fetched = cloud._download(remote_item)
                if hashlib.sha256(fetched).digest() != hashlib.sha256(content).digest():
                    raise CloudError("OneDrive 재다운로드 파일 해시가 원본과 다릅니다.")
                print(f"{label}: 재다운로드 SHA-256 일치 / PASS")
            except CloudError as error:
                print(f"{label}: FAIL · {error}")
                print("시험 파일이 일부 만들어졌을 수도 있습니다. 자동 삭제·재시도하지 않습니다.")
                return 1
        print("PASS: 선택한 OneDrive 완료본 폴더의 시험 파일 업로드/실존/다운로드 검증 완료")
        print("참고: 생성된 시험 파일은 해당 폴더에 남으며, 예배 완료본으로 표시하지 않습니다.")
        return 0
    except CloudError as error:
        print("FAIL: " + str(error))
        return 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True, help="로컬 검수 서버의 작업 DB")
    parser.add_argument("--execute", action="store_true", help="실제 OneDrive에 별도 TEST 파일 업로드")
    parser.add_argument("--sizes", choices=["small", "large", "both"], default="both")
    args = parser.parse_args()
    raise SystemExit(run(args.database, args.execute, args.sizes))


if __name__ == "__main__":
    main()
