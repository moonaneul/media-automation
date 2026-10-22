"""Read-only Git repository inventory; never delete, rename or inspect weekly DBs.

Use:
  python scripts/audit_repository_layout.py
  python scripts/audit_repository_layout.py --json
  python scripts/audit_repository_layout.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_PREFIXES = (
    "experiments/",
    "src/media_automation/_legacy_migration/",
    "scripts/archive/",
)
PRIVATE_PREFIXES = (
    "sources/", "source/", "output/", "outputs/", "input/",
    "data/private/", "assets/private/",
)
ENTRYPOINTS = (
    "webapp.py", "wednesday.py", "friday.py", "sunday.py", "bulletin.py",
    "scripts/start_primary.py", "scripts/run_original_blue.py",
    "src/media_automation/web/original/server.py",
    "src/media_automation/cloud/server.py",
    "src/media_automation/cloud/worker.py",
)
CODE_EXTENSIONS = frozenset({".py", ".js", ".html", ".mjs"})


def tracked_paths(root: Path = ROOT) -> list[str]:
    """Only git-index paths: no walking/output or database contents."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "-z"],
        capture_output=True, check=True,
    )
    return sorted(v.decode("utf-8") for v in result.stdout.split(b"\0") if v)


def classify(path: str) -> str:
    if path.startswith(HISTORICAL_PREFIXES):
        return "historical_reference"
    if path.startswith(".github/"):
        return "automation"
    if path.startswith("tests/"):
        return "regression_tests"
    if path.startswith("docs/"):
        return "documentation"
    if path.startswith("deploy/"):
        return "cloud_infrastructure"
    if path.startswith("src/media_automation/"):
        return "active_application"
    if path.startswith("scripts/"):
        return "maintenance_and_legacy_cli"
    if path.startswith("samples/"):
        return "synthetic_examples"
    if path.startswith("data/"):
        return "public_configuration"
    if path in ENTRYPOINTS:
        return "supported_entrypoints"
    return "project_configuration"


def forbidden_tracked(path: str) -> bool:
    """Do not add weekly originals/outputs/DBs as part of refactors."""
    if path.startswith(PRIVATE_PREFIXES):
        return True
    if path == ".env" or path.startswith(".env."):
        return True
    return path.endswith((".db", ".sqlite", ".sqlite3", ".pem", ".key"))


def exact_historical_copies(paths: list[str], root: Path) -> list[dict[str, str]]:
    """Find confirmed byte-equal code snapshots, without moving either copy."""
    active_hashes: dict[tuple[str, str], list[str]] = defaultdict(list)
    snapshots: list[tuple[str, str]] = []
    for rel in paths:
        file = root / rel
        if file.suffix.lower() not in CODE_EXTENSIONS or not file.is_file():
            continue
        if file.stat().st_size > 1024 * 1024:
            continue
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if classify(rel) == "historical_reference":
            snapshots.append((rel, digest))
        elif classify(rel) in ("active_application", "maintenance_and_legacy_cli"):
            active_hashes[(file.name, digest)].append(rel)
    return [
        {"historical": old, "active": current}
        for old, digest in snapshots
        for current in active_hashes.get((Path(old).name, digest), [])
    ]


def inventory(root: Path = ROOT, paths: list[str] | None = None) -> dict:
    if paths is None:
        paths = tracked_paths(root)
    counts = Counter(classify(path) for path in paths)
    violations = [p for p in paths if forbidden_tracked(p)]
    missing = [p for p in ENTRYPOINTS if p not in paths]
    return {
        "project": "media-automation",
        "tracked_files": len(paths),
        "groups": dict(sorted(counts.items())),
        "historical_reference_paths": [
            p for p in paths if classify(p) == "historical_reference"
            and p.endswith(("README.md", "STAGING_ONLY.md"))
        ],
        "archived_code_exact_copies": exact_historical_copies(paths, root),
        "protected_tracked_paths": violations,
        "missing_supported_entrypoints": missing,
        "files_modified": False,
        "safe_to_delete_anything_automatically": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print structured results")
    parser.add_argument("--check", action="store_true", help="Fail on tracked private inputs or lost supported commands")
    args = parser.parse_args()
    report = inventory()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("Repository structure (read-only, git-index only)")
        for label, total in report["groups"].items():
            print(f"  {label}: {total}")
        print("Verified archival copies also present as active code:", len(report["archived_code_exact_copies"]))
        print("Tracked private-source violations:", len(report["protected_tracked_paths"]))
        print("Missing supported entrypoints:", len(report["missing_supported_entrypoints"]))
        print("No files were moved, removed or written.")
    return 1 if args.check and (
        report["protected_tracked_paths"] or report["missing_supported_entrypoints"]
    ) else 0


if __name__ == "__main__":
    raise SystemExit(main())
