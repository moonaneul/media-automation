"""Shared weekly song-file checklist refresh, without implicit substitutions.

Wednesday and Sunday keep their own field/order policy and CLI messages.
This helper checks only the exact expected file name in the explicitly chosen
directory. It never searches previous weeks or copies/renames any scores.
"""
from pathlib import Path


def refresh_exact_song_files(data: dict, song_dir: Path) -> list[dict]:
    """Update the provided checklist in place; preserve all other weekly fields."""
    items = data.get("items", [])
    for item in items:
        expected = item.get("expected_filename")
        if not expected:
            continue
        candidate = song_dir / expected
        item["file"] = str(candidate) if candidate.is_file() else None
    return items
