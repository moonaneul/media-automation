import pytest
from pptx import Presentation

from media_automation.ppt import (
    FileSongAssetProvider,
    MissingSongAssetError,
    SongAsset,
)


def make_ppt(path):
    Presentation().save(
        path
    )


def test_song_asset_provider_returns_registered_asset(
    tmp_path,
):
    path = (
        tmp_path
        / "song.pptx"
    )

    make_ppt(
        path
    )

    provider = (
        FileSongAssetProvider(
            {
                "찬양": path,
            }
        )
    )

    asset = (
        provider
        .get_song_asset(
            "찬양"
        )
    )

    assert asset.path == path


def test_song_asset_provider_does_not_guess_title(
    tmp_path,
):
    path = (
        tmp_path
        / "song.pptx"
    )

    make_ppt(
        path
    )

    provider = (
        FileSongAssetProvider(
            {
                "주가 보이신 생명의 길": path,
            }
        )
    )

    with pytest.raises(
        MissingSongAssetError
    ):
        provider.get_song_asset(
            "주가보이신생명의길"
        )


def test_song_asset_validates_slide_range(
    tmp_path,
):
    with pytest.raises(
        ValueError
    ):
        SongAsset(
            title="찬양",
            path=(
                tmp_path
                / "song.pptx"
            ),
            start_slide=5,
            end_slide=3,
        )