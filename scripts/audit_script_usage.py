"""Read-only scripts/ entrypoint relationship inventory.

It reports static literal references, NOT proof of runtime use/nonuse.
Never executes an inventoried script, reads real weekly inputs or deletes code.

Usage:
  python scripts/audit_script_usage.py
  python scripts/audit_script_usage.py --json
  python scripts/audit_script_usage.py --check
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_LAUNCHERS = (
    "wednesday.py", "friday.py", "sunday.py", "bulletin.py",
    "webapp.py", "start.command",
)
RISKY_MANUAL_ACTIONS = {
    "sync_workspace.py": "git add --all, git commit and git push when using push",
    "upload_missing_sources.py": "can write original files to a selected OneDrive folder",
    "import_onedrive_connection.py": "can change the encrypted OneDrive connection",
    "export_onedrive_connection.py": "exports connection material; protect the result",
    "export_supabase_works.py": "exports user workspace data; protect the result",
    "package_hosted_runtime.py": "packs runtime assets for a future deployment",
    "prepare_runtime_assets.py": "prepares sensitive local runtime assets",
}


def git_paths(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, check=True,
    )
    return sorted(
        p.decode("utf-8") for p in result.stdout.split(b"\0") if p
    )


def referenced_scripts(file: Path, known: set[str]) -> set[str]:
    """Find literal references to script filenames, not guessed call paths."""
    if not file.is_file():
        return set()
    try:
        content = file.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return set()
    if file.suffix == ".py":
        try:
            tree = ast.parse(content, filename=str(file))
        except SyntaxError:
            return set()
        values = (
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    else:
        values = content.splitlines()
    found = set()
    for value in values:
        for script in known:
            if script in value:
                found.add(script)
    return found


def audit(root: Path = ROOT, *, paths: list[str] | None = None) -> dict:
    paths = git_paths(root) if paths is None else paths
    scripts = sorted(
        path for path in paths
        if path.startswith("scripts/") and path.endswith(".py")
        and not path.startswith("scripts/archive/")
    )
    known_names = {Path(p).name for p in scripts}
    if len(known_names) != len(scripts):
        raise ValueError("Script names are not unique; manual disambiguation needed")
    by_name = {Path(p).name: p for p in scripts}
    root_reachable: set[str] = set()
    queue = []
    for launcher in ROOT_LAUNCHERS:
        for name in referenced_scripts(root / launcher, known_names):
            queue.append(name)
    while queue:
        name = queue.pop()
        if name in root_reachable:
            continue
        root_reachable.add(name)
        queue.extend(
            referenced_scripts(root / by_name[name], known_names)
            - root_reachable
        )

    workflows = [
        p for p in paths
        if p.startswith(".github/workflows/") and p.endswith((".yml", ".yaml"))
    ]
    ci_referenced: set[str] = set()
    for workflow in workflows:
        ci_referenced |= referenced_scripts(root / workflow, known_names)

    results = []
    for script in scripts:
        name = Path(script).name
        matches = []
        if name in root_reachable:
            matches.append("referenced_by_root_cli_chain")
        if name in ci_referenced:
            matches.append("mentioned_in_github_workflow")
        if not matches:
            matches.append("standalone_or_unresolved_static_reference")
        results.append({
            "path": script,
            "evidence": matches,
            "manual_safety_review": RISKY_MANUAL_ACTIONS.get(name),
            "delete_without_manual_review": False,
        })
    archived = sorted(p for p in paths if p.startswith("scripts/archive/") and p.endswith(".py"))
    return {
        "tracked_active_directory_py": len(scripts),
        "tracked_archive_py": len(archived),
        "referenced_by_root_cli_chain": len(root_reachable),
        "mentioned_in_github_workflow": len(ci_referenced),
        "standalone_or_unresolved_static_reference": sum(
            len(item["evidence"]) == 1
            and item["evidence"][0] == "standalone_or_unresolved_static_reference"
            for item in results
        ),
        "scripts": results,
        "archived_reference_scripts": archived,
        "has_deleted_or_changed_any_file": False,
        "static_reference_alone_approves_deletion": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    report = audit()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for key, value in report.items():
            if isinstance(value, int):
                print(f"{key}: {value}")
        for item in report["scripts"]:
            category = ", ".join(item["evidence"])
            safety = " · REVIEW BEFORE RUN" if item["manual_safety_review"] else ""
            print(f"{item['path']}: {category}{safety}")
        print("No repository files or weekly data were changed.")
    if args.check:
        if len(report["scripts"]) != report["tracked_active_directory_py"]:
            return 1
        if any(item["delete_without_manual_review"] for item in report["scripts"]):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
