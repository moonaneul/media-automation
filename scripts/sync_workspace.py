"""Sync code and worship files together, including Git LFS media."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="예배 작업 전체 동기화")
    parser.add_argument("action", choices=["push", "pull"])
    parser.add_argument("--message", default="Sync worship workspace")
    args = parser.parse_args()
    run("git", "lfs", "version")
    run("git", "lfs", "install")
    if args.action == "pull":
        run("git", "pull", "--ff-only")
        run("git", "lfs", "pull")
    else:
        run("git", "add", "--all")
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], cwd=ROOT
        )
        if result.returncode == 1:
            run("git", "commit", "-m", args.message)
        elif result.returncode != 0:
            raise SystemExit(result.returncode)
        run("git", "push")
    print("SYNC: PASS")


if __name__ == "__main__":
    main()
