from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize("system", ["Darwin", "Linux", "Windows"])
def test_complete_dispatches_production_build_on_supported_platforms(monkeypatch, system):
    script = Path(__file__).resolve().parents[1] / "sunday.py"
    spec = spec_from_file_location("sunday_cli", script)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    source = script.parent / "input/sunday/20260927/source_rehearsal.pptx"
    calls = []
    monkeypatch.setattr(module.platform, "system", lambda: system)
    monkeypatch.setattr(module, "_resolved_source", lambda value: source)
    monkeypatch.setattr(module, "run_script", lambda *args: calls.append(args))

    module.complete(SimpleNamespace(date="2026-09-27", source=str(source)))

    assert calls == [("complete_sunday_week.py", "--date", "2026-09-27", "--source", str(source))]
