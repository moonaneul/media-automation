"""Read-only Mac/Windows checkout and local-data boundary check.

No database queries, cloud requests, credential reads, file writes or Git mutations.
Do not use this report as approval to delete directories or synchronize private data.

Usage:
  python scripts/check_workspace_split.py
  python scripts/check_workspace_split.py --json
  python scripts/check_workspace_split.py --json --compare /path/to/other-device-report.json
  python scripts/check_workspace_split.py --root /path/to/existing/checkout --check
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_PREFIXES = (
    "sources/", "source/", "input/", "output/", "outputs/",
    "data/private/", "assets/private/",
)
IGNORED_PATHS = (
    "sources/", "source/", "input/", "output/", "outputs/",
    "data/private/", "assets/private/",
)
SENSITIVE_EXTENSIONS = (".db", ".sqlite", ".sqlite3", ".pem", ".key")
PRIVATE_LOCATIONS = {
    "sources": "sources",
    "weekly_inputs": "input",
    "local_work_and_generated": "output",
    "private_bible": "data/private",
    "private_assets": "assets/private",
}


def _git(root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        check=False, timeout=20,
    )
    if check and result.returncode:
        raise ValueError("Git 작업 폴더 상태를 확인할 수 없습니다.")
    return result.stdout if result.returncode == 0 else b""


def _is_sensitive(path: str) -> bool:
    cleaned = path.replace("\\", "/")
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]
    return (
        cleaned.startswith(PRIVATE_PREFIXES)
        or cleaned == ".env"
        or cleaned.startswith(".env.")
        or cleaned.lower().endswith(SENSITIVE_EXTENSIONS)
    )


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _selection(root: Path, env: dict[str, str]) -> dict:
    """Inspect path existence only; NEVER connect to SQLite or scan the output tree."""
    if env.get("MEDIA_DATABASE"):
        source = "MEDIA_DATABASE"
        path = Path(env["MEDIA_DATABASE"]).expanduser()
        # Explicit relative paths are resolved from the current process working dir.
        if not path.is_absolute():
            path = Path.cwd() / path
    else:
        pointer = root / "output" / "main-database.txt"
        if pointer.is_file():
            source = "output/main-database.txt"
            # Bound read: this is a local pathname, not database or connection bytes.
            value = pointer.read_text(encoding="utf-8").strip() if pointer.stat().st_size <= 4096 else ""
            if not value:
                return {
                    "source": source, "selected_database_exists": False,
                    "selected_database_within_checkout": None,
                    "selection_problem": "pointer_missing_or_invalid",
                    "database_contents_inspected": False,
                }
            path = Path(value).expanduser()
            if not path.is_absolute():
                path = root / path
        else:
            source = "fallback"
            unified = root / "output" / "unified-work" / "work.db"
            path = unified if unified.is_file() else root / "output" / "web" / "work.db"
    return {
        "source": source,
        "selected_database_exists": path.is_file(),
        "selected_database_within_checkout": _inside(path, root),
        "selection_problem": None,
        "database_contents_inspected": False,
    }


def collect(root: Path = ROOT, environ: dict[str, str] | None = None) -> dict:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError("지정한 체크아웃 폴더가 존재하지 않습니다.")
    top = Path(_git(root, "rev-parse", "--show-toplevel").decode("utf-8").strip()).resolve()
    if top != root:
        raise ValueError("Git 최상위 체크아웃 폴더를 --root로 지정하세요.")
    branch = _git(root, "symbolic-ref", "--short", "HEAD", check=False).decode("utf-8").strip()
    sha = _git(root, "rev-parse", "HEAD").decode("ascii").strip()
    # Ignore all status file names; they may contain user names or church notices.
    porcelain = _git(root, "status", "--porcelain=v1", "--untracked-files=normal", "-z")
    entries = [item for item in porcelain.split(b"\0") if item]
    staged = sum(item[:1] not in (b" ", b"?") for item in entries)
    unstaged = sum(item[1:2] not in (b" ", b"?") for item in entries)
    untracked = sum(item.startswith(b"??") for item in entries)

    tracked = [p.decode("utf-8", errors="replace") for p in
               _git(root, "ls-files", "-z").split(b"\0") if p]
    tracked_private = sum(_is_sensitive(p) for p in tracked)
    ignored = {}
    for path in IGNORED_PATHS:
        code = subprocess.run(
            ["git", "-C", str(root), "check-ignore", "-q", "--", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            check=False, timeout=10,
        ).returncode
        ignored[path.rstrip("/")] = code == 0
    env = dict(os.environ) if environ is None else environ
    data = {label: (root / dirname).exists()
            for label, dirname in PRIVATE_LOCATIONS.items()}
    selected = _selection(root, env)
    warnings = []
    if entries:
        warnings.append("uncommitted_or_untracked_code_requires_review")
    if tracked_private:
        warnings.append("private_or_database_file_tracked_by_git")
    if not all(ignored.values()):
        warnings.append("one_or_more_private_directory_ignore_guards_missing")
    if selected["selection_problem"] or not selected["selected_database_exists"]:
        warnings.append("selected_local_database_not_confirmed")
    if selected["selected_database_exists"] and selected["selected_database_within_checkout"] is False:
        warnings.append("selected_local_database_outside_checkout_check_intended_path")

    return {
        "schema": "media-automation/workspace-split-v1",
        "git": {
            "branch": branch or "detached",
            "head_sha": sha,
            "has_local_changes": bool(entries),
            "staged_entries": staged,
            "unstaged_entries": unstaged,
            "untracked_entries": untracked,
            "tracked_private_entries": tracked_private,
        },
        "protected_directories_ignored": ignored,
        "local_directories_present": data,
        "database": selected,
        "code_review_before_pull_or_switch_required": bool(entries),
        "warnings": warnings,
        "data_was_copied_or_synced": False,
        "db_content_or_bible_text_examined": False,
        "files_written_or_deleted": False,
    }


def compare(local: dict, other: dict) -> dict:
    if not isinstance(other, dict) or other.get("schema") != local["schema"]:
        raise ValueError("호환되지 않는 비교 보고서입니다.")
    first, second = local["git"], other["git"]
    return {
        "branches_match": first["branch"] == second["branch"],
        "code_commits_match": first["head_sha"] == second["head_sha"],
        "both_worktrees_clean": not (
            first["has_local_changes"] or second["has_local_changes"]
        ),
        "either_has_tracked_private_files": bool(
            first["tracked_private_entries"] or second["tracked_private_entries"]
        ),
        "both_have_local_database_path": bool(
            local["database"]["selected_database_exists"]
            and other["database"]["selected_database_exists"]
        ),
        "database_data_equality_verified": False,
        "private_data_auto_sync_performed": False,
        "next_action": (
            "review_local_changes_before_git_sync"
            if first["has_local_changes"] or second["has_local_changes"]
            else "compare_branches_and_commits_before_code_pull"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="Existing checkout; never clone or create a folder")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compare", type=Path, help="Other device's redacted JSON report")
    parser.add_argument("--check", action="store_true",
                        help="Fail only on lost private Git ignore guards or tracked secrets")
    args = parser.parse_args()
    try:
        state = collect(args.root)
        if args.compare:
            other = json.loads(args.compare.read_text(encoding="utf-8-sig"))
            state["comparison"] = compare(state, other)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(state, ensure_ascii=False, indent=2))
    else:
        print("WORKSPACE SPLIT — READ ONLY")
        print("branch:", state["git"]["branch"])
        print("commit:", state["git"]["head_sha"][:12])
        print("local changes:", state["git"]["has_local_changes"],
              "(staged", state["git"]["staged_entries"],
              "unstaged", state["git"]["unstaged_entries"],
              "untracked", state["git"]["untracked_entries"], ")")
        print("Git tracked private files:", state["git"]["tracked_private_entries"])
        print("private path ignore guards:", all(state["protected_directories_ignored"].values()))
        print("selected local DB exists:", state["database"]["selected_database_exists"],
              "via", state["database"]["source"])
        if "comparison" in state:
            print("commits match:", state["comparison"]["code_commits_match"])
            print("DB contents compared: False")
        for warning in state["warnings"]:
            print("review:", warning)
        print("No original, database, token or Git state was modified.")
    if args.check and (
        state["git"]["tracked_private_entries"]
        or not all(state["protected_directories_ignored"].values())
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
