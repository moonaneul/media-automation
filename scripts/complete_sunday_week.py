from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
INTAKE = ROOT / "output" / "sunday_intake"
OUTPUT = ROOT / "output" / "sunday"
PRE_SERVICE_SLIDES = 4


def token(date_value: str) -> str:
    return date_value.replace("-", "").replace(".", "").strip()


def run_script(name: str, *args: str) -> None:
    cmd = [sys.executable, str(SCRIPTS / name), *args]
    print("\n>>>", " ".join(cmd))
    result = subprocess.run(cmd, cwd=ROOT, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def load_build_sunday_module():
    path = SCRIPTS / "build_sunday.py"
    spec = importlib.util.spec_from_file_location(
        "media_automation_build_sunday",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"build_sunday.py를 불러올 수 없습니다: {path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(
        description="현재 운영 규칙으로 주일 오전 2부 PPT를 조립합니다."
    )
    parser.add_argument("--date", required=True)
    parser.add_argument(
        "--source",
        required=True,
        type=Path,
        help="과거 주일 오전 2부 PPT. 예배 전 안내 1~4장만 사용합니다.",
    )
    parser.add_argument(
        "--structure-only",
        action="store_true",
        help="악보는 장수만 반영한 구조 프리뷰를 생성합니다.",
    )
    args = parser.parse_args()

    source = args.source.expanduser()
    if not source.is_absolute():
        source = (Path.cwd() / source).resolve()
    if not source.exists():
        raise SystemExit(f"ERROR: 주일 원본 PPT를 찾을 수 없습니다: {source}")

    date_token = token(args.date)

    run_script(
        "resume_sunday_week.py",
        "--date",
        args.date,
    )

    weekly = INTAKE / f"sunday-{date_token}.yaml"
    bible = INTAKE / f"sunday-{date_token}-bible.yaml"
    songs = INTAKE / f"sunday-{date_token}-songs.yaml"

    for name, path in {
        "weekly": weekly,
        "bible": bible,
        "songs": songs,
    }.items():
        if not path.exists():
            raise SystemExit(f"ERROR: {name} 입력이 준비되지 않았습니다: {path}")

    OUTPUT.mkdir(parents=True, exist_ok=True)

    suffix = "_구조프리뷰.pptx" if args.structure_only else "_주일예배.pptx"
    output = OUTPUT / f"{date_token}{suffix}"

    # 기존 build_sunday.py는 2026년 1월 과거 자료 구조를 보존한다.
    # 실제 운영 조립에서는 현재 규칙(주요 순서 사이 빈 화면 1장)을 적용한다.
    from media_automation.planning.sunday_policy import (
        build_current_sunday_plan,
    )

    module = load_build_sunday_module()
    module.build_sunday_plan = build_current_sunday_plan

    build_args = [
        str(SCRIPTS / "build_sunday.py"),
        "--weekly",
        str(weekly),
        "--songs",
        str(songs),
        "--bible",
        str(bible),
        "--source",
        str(source),
        "--pre-service-slides",
        str(PRE_SERVICE_SLIDES),
        "--output",
        str(output),
    ]

    if args.structure_only:
        build_args.append("--structure-only")

    old_argv = sys.argv
    try:
        sys.argv = build_args
        module.main()
    finally:
        sys.argv = old_argv

    print("\n=== SUNDAY COMPLETE WRAPPER ===")
    print(f"date       : {args.date}")
    print(f"source     : {source}")
    print(f"pre-service: 1-{PRE_SERVICE_SLIDES}")
    print(f"output     : {output}")
    if args.structure_only:
        print("mode       : structure preview")
    else:
        print("mode       : production merge")


if __name__ == "__main__":
    main()
