from pathlib import Path

import pytest

from media_automation.ppt import (
    InvalidZoomMediaAssetError,
    MissingZoomMediaAssetError,
    load_zoom_media_asset_provider,
)


def test_zoom_media_manifest_resolves_relative_paths(
    tmp_path,
):
    media_dir = tmp_path / "media"
    media_dir.mkdir()

    video = media_dir / "song.mp4"
    audio = media_dir / "song.mp3"

    video.write_bytes(b"video")
    audio.write_bytes(b"audio")

    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  예시 찬양:
    video: media/song.mp4
    audio: media/song.mp3
""",
        encoding="utf-8",
    )

    provider = (
        load_zoom_media_asset_provider(
            manifest
        )
    )

    asset = provider.get_media_asset(
        "예시 찬양"
    )

    assert asset.video_path == video
    assert asset.audio_path == audio


def test_zoom_media_audio_is_optional(
    tmp_path,
):
    video = tmp_path / "song.mp4"
    video.write_bytes(b"video")

    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  예시 찬양:
    video: song.mp4
""",
        encoding="utf-8",
    )

    provider = (
        load_zoom_media_asset_provider(
            manifest
        )
    )

    asset = provider.get_media_asset(
        "예시 찬양"
    )

    assert asset.video_path == video
    assert asset.audio_path is None


def test_zoom_media_missing_video_fails(
    tmp_path,
):
    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  예시 찬양:
    video: missing.mp4
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
        match="영상 파일",
    ):
        provider.get_media_asset(
            "예시 찬양"
        )


def test_zoom_media_empty_video_fails(
    tmp_path,
):
    video = tmp_path / "empty.mp4"
    video.touch()

    manifest = tmp_path / "zoom-media.yaml"

    manifest.write_text(
        """
media:
  예시 찬양:
    video: empty.mp4
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
            "예시 찬양"
        )