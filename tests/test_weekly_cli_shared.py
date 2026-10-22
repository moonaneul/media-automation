"""Regression tests for shared non-destructive weekly CLI helpers."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from media_automation.weekly_cli import load_optional_yaml, weekly_token

ROOT = Path(__file__).resolve().parents[1]


def _load_entrypoint(name):
    spec = importlib.util.spec_from_file_location("weekly_" + name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("raw,expected", [
    ("2026-10-22", "20261022"),
    ("2026.10.22", "20261022"),
    (" 2026-10-22 ", "20261022"),
    ("20261022", "20261022"),
])
def test_shared_weekly_filename_token_preserves_existing_format(raw, expected):
    assert weekly_token(raw) == expected
    for name in ("wednesday", "friday", "sunday"):
        cli = _load_entrypoint(name)
        assert cli.token(raw) == expected
        assert cli.token is weekly_token


def test_optional_yaml_reader_does_not_create_or_infer_missing_input(tmp_path):
    missing = tmp_path / "no-weekly-file.yaml"
    assert load_optional_yaml(missing) == {}
    assert not missing.exists()
    for name in ("wednesday", "friday", "sunday"):
        assert _load_entrypoint(name).load_yaml(missing) == {}
    assert not missing.exists()


def test_shared_yaml_reader_preserves_korean_and_three_state_fields(tmp_path):
    path = tmp_path / "weekly.yaml"
    payload = {
        "date": "2026-10-22",
        "fields": {
            "기도 담당자": {"state": "NONE", "value": ""},
            "설교 제목": {"state": "UNSET", "value": ""},
            "성경 본문": {"state": "VALUE", "value": "요 3:16"},
        },
    }
    path.write_text("\ufeff" + yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")
    before = path.read_bytes()
    assert load_optional_yaml(path) == payload
    assert path.read_bytes() == before


def test_invalid_yaml_does_not_turn_into_fabricated_current_week_values(tmp_path):
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text("fields: [invalid\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        load_optional_yaml(invalid)


@pytest.mark.parametrize("service", ["wednesday", "friday", "sunday"])
def test_existing_weekly_commands_still_expose_help_without_network_or_data(service):
    result = subprocess.run(
        [sys.executable, str(ROOT / (service + ".py")), "--help"],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()
