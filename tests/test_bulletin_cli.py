from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
BULLETIN_PATH = ROOT / "bulletin.py"

spec = spec_from_file_location("bulletin_cli", BULLETIN_PATH)
assert spec is not None
assert spec.loader is not None
bulletin = module_from_spec(spec)
spec.loader.exec_module(bulletin)


def configure_roots(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        bulletin,
        "INPUT_ROOT",
        tmp_path / "input" / "bulletin",
    )
    monkeypatch.setattr(
        bulletin,
        "SUNDAY_ROOT",
        tmp_path / "output" / "sunday_intake",
    )
    monkeypatch.setattr(
        bulletin,
        "WORK_ROOT",
        tmp_path / "output" / "bulletin_intake",
    )
    monkeypatch.setattr(
        bulletin,
        "OUTPUT_ROOT",
        tmp_path / "output" / "bulletin",
    )
    monkeypatch.setattr(
        bulletin,
        "ANCHOR_PATH",
        tmp_path / "data" / "bulletin_number_anchor.yaml",
    )


def write_transfer(
    date_value: str,
    text: str,
) -> Path:
    path = bulletin.week_dir(date_value) / "transfer.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_sunday(
    date_value: str,
    data: dict | None = None,
) -> Path:
    path = bulletin.sunday_path(date_value)
    path.parent.mkdir(parents=True, exist_ok=True)

    if data is None:
        data = {
            "service": "sunday",
            "date": date_value,
            "bulletin": {},
        }

    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path


def test_complete_blocks_when_transfer_is_missing(
    tmp_path,
    monkeypatch,
):
    configure_roots(monkeypatch, tmp_path)

    args = SimpleNamespace(
        date="2026-10-04",
        output=None,
    )

    with pytest.raises(
        SystemExit,
        match="전달 주보가 없습니다",
    ):
        bulletin.complete(args)


def test_complete_blocks_when_sunday_yaml_is_missing(
    tmp_path,
    monkeypatch,
):
    configure_roots(monkeypatch, tmp_path)

    write_transfer(
        "2026-10-04",
        "10/4\n",
    )

    args = SimpleNamespace(
        date="2026-10-04",
        output=None,
    )

    with pytest.raises(
        SystemExit,
        match="Sunday YAML이 준비되지 않았습니다",
    ):
        bulletin.complete(args)


def test_number_is_calculated_from_anchor(
    tmp_path,
    monkeypatch,
):
    configure_roots(monkeypatch, tmp_path)

    bulletin.save_anchor(
        "2026-10-04",
        "13-40",
    )

    number, source, anchor = bulletin.resolve_number(
        "2026-10-11",
        {
            "date": "2026-10-11",
            "bulletin_number": None,
        },
    )

    assert number == "13-41"
    assert source == "AUTO"
    assert anchor == "2026-10-04 = 13-40"


def test_status_never_ready_when_transfer_date_is_wrong(
    tmp_path,
    monkeypatch,
    capsys,
):
    configure_roots(monkeypatch, tmp_path)

    write_transfer(
        "2026-10-04",
        "10/11\n",
    )
    write_sunday("2026-10-04")

    bulletin.save_state(
        "2026-10-04",
        {
            "date": "2026-10-04",
            "bulletin_number": "13-40",
        },
    )

    args = SimpleNamespace(
        date="2026-10-04",
    )

    bulletin.status(args)

    output = capsys.readouterr().out

    assert "date     : ERROR" in output
    assert "BULLETIN INPUTS NOT READY" in output
    assert "BULLETIN INPUTS READY\n" not in output


def test_number_is_saved_in_state(
    tmp_path,
    monkeypatch,
):
    configure_roots(monkeypatch, tmp_path)

    bulletin.save_state(
        "2026-10-04",
        {
            "date": "2026-10-04",
            "bulletin_number": None,
        },
    )

    args = SimpleNamespace(
        date="2026-10-04",
        number="No. 13-40",
    )

    bulletin.set_number(args)

    state = bulletin.load_yaml(
        bulletin.state_path("2026-10-04")
    )

    assert state["bulletin_number"] == "13-40"


def test_complete_keeps_original_sunday_and_writes_number_only_to_derived(
    tmp_path,
    monkeypatch,
):
    configure_roots(monkeypatch, tmp_path)

    write_transfer(
        "2026-10-04",
        "10/4\n",
    )

    original_data = {
        "service": "sunday",
        "date": "2026-10-04",
        "bulletin": {
            "number": {
                "status": "UNSET",
            },
        },
    }

    sunday = write_sunday(
        "2026-10-04",
        original_data,
    )
    original_text = sunday.read_text(
        encoding="utf-8"
    )

    bulletin.save_state(
        "2026-10-04",
        {
            "date": "2026-10-04",
            "bulletin_number": "13-40",
        },
    )

    captured = {}

    def fake_build_bulletin_from_files(
        *,
        sunday_yaml,
        transfer_source,
        output_pdf,
    ):
        captured["sunday_yaml"] = sunday_yaml
        captured["transfer_source"] = transfer_source
        captured["output_pdf"] = output_pdf

        return SimpleNamespace(
            pdf=SimpleNamespace(
                path=output_pdf,
            ),
            merge=SimpleNamespace(
                praise_raw=SimpleNamespace(
                    value=None,
                ),
            ),
        )

    monkeypatch.setattr(
        bulletin,
        "build_bulletin_from_files",
        fake_build_bulletin_from_files,
    )

    args = SimpleNamespace(
        date="2026-10-04",
        output=None,
    )

    bulletin.complete(args)

    assert sunday.read_text(
        encoding="utf-8"
    ) == original_text

    original_after = yaml.safe_load(
        sunday.read_text(encoding="utf-8")
    )
    assert (
        original_after["bulletin"]["number"]["status"]
        == "UNSET"
    )

    derived = bulletin.WORK_ROOT / (
        "sunday-20261004-bulletin.yaml"
    )
    assert derived.exists()

    derived_data = yaml.safe_load(
        derived.read_text(encoding="utf-8")
    )

    assert derived_data["bulletin"]["number"] == {
        "status": "VALUE",
        "value": "13-40",
    }

    assert captured["sunday_yaml"] == derived
    assert (
        captured["transfer_source"]
        == bulletin.week_dir("2026-10-04")
        / "transfer.txt"
    )
    assert (
        captured["output_pdf"]
        == bulletin.OUTPUT_ROOT
        / "20261004_주보.pdf"
    )
