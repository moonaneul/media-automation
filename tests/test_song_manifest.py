import pytest
from pptx import Presentation

from media_automation.ppt import (
    MissingSongAssetError,
    load_song_asset_provider,
)


def make_ppt(path):
    Presentation().save(
        path
    )


def test_manifest_loads_simple_song(
    tmp_path,
):
    song = (
        tmp_path
        / "song.pptx"
    )

    make_ppt(
        song
    )

    manifest = (
        tmp_path
        / "songs.yaml"
    )

    manifest.write_text(
        """
songs:
  테스트 찬양: song.pptx
""".strip(),
        encoding="utf-8",
    )

    provider = (
        load_song_asset_provider(
            manifest
        )
    )

    asset = provider.get_song_asset(
        "테스트 찬양"
    )

    assert asset.path == song


def test_manifest_does_not_guess_song(
    tmp_path,
):
    song = (
        tmp_path
        / "song.pptx"
    )

    make_ppt(
        song
    )

    manifest = (
        tmp_path
        / "songs.yaml"
    )

    manifest.write_text(
        """
songs:
  정확한 제목: song.pptx
""".strip(),
        encoding="utf-8",
    )

    provider = (
        load_song_asset_provider(
            manifest
        )
    )

    with pytest.raises(
        MissingSongAssetError
    ):
        provider.get_song_asset(
            "비슷한 제목"
        )


def test_manifest_requires_songs(
    tmp_path,
):
    manifest = (
        tmp_path
        / "songs.yaml"
    )

    manifest.write_text(
        "{}",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        load_song_asset_provider(
            manifest
        )


def test_manifest_loads_slide_range(
    tmp_path,
):
    song = (
        tmp_path
        / "service.pptx"
    )

    make_ppt(
        song
    )

    manifest = (
        tmp_path
        / "songs.yaml"
    )

    manifest.write_text(
        """
songs:
  주가 보이신 생명의 길:
    path: service.pptx
    slides: [22, 26]
""".strip(),
        encoding="utf-8",
    )

    provider = (
        load_song_asset_provider(
            manifest
        )
    )

    asset = provider.get_song_asset(
        "주가 보이신 생명의 길"
    )

    assert (
        asset.start_slide
        == 22
    )

    assert (
        asset.end_slide
        == 26
    )


def test_manifest_rejects_invalid_range(
    tmp_path,
):
    song = (
        tmp_path
        / "service.pptx"
    )

    make_ppt(
        song
    )

    manifest = (
        tmp_path
        / "songs.yaml"
    )

    manifest.write_text(
        """
songs:
  잘못된 찬양:
    path: service.pptx
    slides: [26, 22]
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError
    ):
        load_song_asset_provider(
            manifest
        )