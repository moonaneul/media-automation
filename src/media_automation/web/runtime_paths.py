"""Portable paths for the local media automation operator.

Only the *default* job storage location changes. The --storage command-line
option still overrides it. No private data is copied or inspected here.
"""
from __future__ import annotations

import os
from pathlib import Path
import platform
from typing import Mapping


def default_jobs_root(*, os_name: str | None = None,
                      home: Path | None = None,
                      env: Mapping[str, str] | None = None) -> Path:
    """Return an OS-native, per-user persistent jobs folder (not created)."""
    operating_system = os_name or platform.system()
    home = Path.home() if home is None else Path(home)
    env = os.environ if env is None else env
    custom = env.get('MEDIA_AUTOMATION_JOBS_DIR', '').strip()
    if custom:
        candidate = Path(custom).expanduser()
        if not candidate.is_absolute():
            raise ValueError('MEDIA_AUTOMATION_JOBS_DIR must be an absolute path')
        return candidate
    if operating_system == 'Darwin':
        return home / 'Library' / 'Application Support' / 'media-automation' / 'jobs'
    if operating_system == 'Windows':
        basedir = env.get('LOCALAPPDATA', '').strip()
        base = Path(basedir) if basedir else home / 'AppData' / 'Local'
        return base / 'media-automation' / 'jobs'
    state_home = env.get('XDG_STATE_HOME', '').strip()
    base = Path(state_home).expanduser() if state_home else home / '.local' / 'state'
    if not base.is_absolute():
        raise ValueError('XDG_STATE_HOME must be an absolute path')
    return base / 'media-automation' / 'jobs'
