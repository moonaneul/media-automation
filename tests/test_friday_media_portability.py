from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import shutil


def test_repository_media_paths_survive_moving_workspace(tmp_path, monkeypatch):
    spec = spec_from_file_location(
        "set_friday_zoom_media",
        Path(__file__).resolve().parents[1] / "scripts/set_friday_zoom_media.py",
    )
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    original = tmp_path / "computer_a"
    media = original / "input/friday_zoom/20261009/opening_song_1.mp4"
    media.parent.mkdir(parents=True)
    media.write_bytes(b"test media")
    monkeypatch.chdir(original)
    relative = module.normalize_path(media)
    assert not Path(relative).is_absolute()
    moved = tmp_path / "computer_b"
    shutil.copytree(original, moved)
    assert (moved / "output" / relative).resolve().read_bytes() == b"test media"
