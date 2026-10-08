from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import yaml

from media_automation.ppt import create_4x3_presentation


def test_validate_only_does_not_merge_or_overwrite_final(tmp_path, monkeypatch, capsys):
    spec = spec_from_file_location(
        "build_wednesday_operational",
        Path(__file__).resolve().parents[1] / "scripts/build_wednesday_operational.py",
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    weekly = {
        "service": "wednesday", "date": "2026-09-30",
        "opening_songs": [{"status": "NONE"}] * 3,
        "prayer": {"status": "VALUE", "person": "한송희"},
        "additional_song": {"status": "NONE"},
        "scripture": {"status": "VALUE", "reference": "요 3:16"},
        "sermon_title": {"status": "VALUE", "text": "제목"},
        "additional_scripture": {"status": "NONE"},
        "decision_hymn": {"status": "NONE"},
    }
    files = {
        "weekly": weekly, "songs": {"songs": {}},
        "bible": {"passages": {"요 3:16": {"reference": "요 3:16", "verses": {16: "본문"}}}},
    }
    arguments = ["build_wednesday_operational.py"]
    for name, data in files.items():
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        arguments.extend([f"--{name}", str(path)])
    source = tmp_path / "source.pptx"
    prs = create_4x3_presentation()
    for _ in range(4):
        prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(source)
    final = tmp_path / "final.pptx"
    final.write_bytes(b"previous final must remain unchanged")
    arguments.extend(["--source", str(source), "--output", str(final), "--validate-only"])
    monkeypatch.setattr(sys, "argv", arguments)

    def forbidden_merger():
        raise AssertionError("Validation must not invoke PowerPoint")

    monkeypatch.setattr(module, "create_platform_slide_merger", forbidden_merger)
    module.main()
    assert final.read_bytes() == b"previous final must remain unchanged"
    assert (tmp_path / "final_structure_check.pptx").exists()
    assert "Wednesday Input / Structure QA: PASS" in capsys.readouterr().out
