import pytest

from media_automation.ppt import (
    InvalidZoomMediaAssetError,
    MissingZoomMediaAssetError,
    ZoomMediaType,
    load_zoom_media_asset_provider,
)


def test_zoom_video_asset(
    tmp_path,
):
    video = tmp_path / "song.mp4"
    video.write_bytes(b"video")

    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  opening_song_1:
    type: video
    title: 예시 찬양
    path: song.mp4
""",
        encoding="utf-8",
    )

    provider = (
        load_zoom_media_asset_provider(
            manifest
        )
    )

    asset = provider.get_media_asset(
        "opening_song_1"
    )

    assert (
        asset.media_type
        == ZoomMediaType.VIDEO
    )
    assert asset.title == "예시 찬양"
    assert asset.path == video


def test_zoom_audio_asset(
    tmp_path,
):
    audio = tmp_path / "prayer.mp3"
    audio.write_bytes(b"audio")

    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  first_prayer_audio:
    type: audio
    path: prayer.mp3
""",
        encoding="utf-8",
    )

    provider = (
        load_zoom_media_asset_provider(
            manifest
        )
    )

    asset = provider.get_media_asset(
        "first_prayer_audio"
    )

    assert (
        asset.media_type
        == ZoomMediaType.AUDIO
    )
    assert asset.title is None
    assert asset.path == audio


def test_zoom_media_missing_file_fails(
    tmp_path,
):
    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  opening_song_1:
    type: video
    title: 예시 찬양
    path: missing.mp4
""",
        encoding="utf-8",
    )

    provider = (
        load_zoom_media_asset_provider(
            manifest
        )
    )

    with pytest.raises(
        MissingZoomMediaAssetError,
        match="미디어 파일",
    ):
        provider.get_media_asset(
            "opening_song_1"
        )


def test_zoom_media_empty_file_fails(
    tmp_path,
):
    video = tmp_path / "empty.mp4"
    video.touch()

    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  opening_song_1:
    type: video
    title: 예시 찬양
    path: empty.mp4
""",
        encoding="utf-8",
    )

    provider = (
        load_zoom_media_asset_provider(
            manifest
        )
    )

    with pytest.raises(
        InvalidZoomMediaAssetError,
        match="비어 있습니다",
    ):
        provider.get_media_asset(
            "opening_song_1"
        )