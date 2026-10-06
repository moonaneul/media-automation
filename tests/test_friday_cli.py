from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRIDAY_PATH = ROOT / "friday.py"

spec = spec_from_file_location("friday_cli", FRIDAY_PATH)
assert spec is not None
assert spec.loader is not None
friday = module_from_spec(spec)
spec.loader.exec_module(friday)


def test_clipboard_command_uses_pbpaste_on_macos(monkeypatch):
    monkeypatch.setattr(friday.platform, "system", lambda: "Darwin")
    assert friday.clipboard_command() == ["pbpaste"]


def test_clipboard_command_uses_powershell_on_windows(monkeypatch):
    monkeypatch.setattr(friday.platform, "system", lambda: "Windows")
    command = friday.clipboard_command()
    assert command[:3] == ["powershell.exe", "-NoProfile", "-Command"]
    assert "Get-Clipboard -Raw" in command[3]
