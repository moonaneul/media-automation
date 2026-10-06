import friday


def test_clipboard_command_uses_pbpaste_on_macos(monkeypatch):
    monkeypatch.setattr(friday.platform, "system", lambda: "Darwin")
    assert friday.clipboard_command() == ["pbpaste"]


def test_clipboard_command_uses_powershell_on_windows(monkeypatch):
    monkeypatch.setattr(friday.platform, "system", lambda: "Windows")
    command = friday.clipboard_command()
    assert command[:3] == ["powershell.exe", "-NoProfile", "-Command"]
    assert "Get-Clipboard -Raw" in command[3]
