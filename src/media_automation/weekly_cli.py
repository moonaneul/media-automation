"""Shared, side-effect-free helpers for the three weekly command-line tools.

Do not move per-service commands or input/ folders into this module:
wednesday, friday and sunday retain independent worship formats and workflows.
"""
from pathlib import Path

import yaml


def weekly_token(date_value: str) -> str:
    """Preserve the historic Wednesday/Friday/Sunday filename convention."""
    return date_value.replace("-", "").replace(".", "").strip()


def load_optional_yaml(path: Path) -> object:
    """Read an optional UTF-8 weekly YAML without creating files or defaults."""
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
