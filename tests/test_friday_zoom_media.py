from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)
from media_automation.ppt import (
    ZoomMediaType,
    get_friday_zoom_media_key,
    get_friday_zoom_media_type,
)


def test_zoom_song_uses_block_key_as_video_key():
    block = WorshipBlock(
        kind=BlockKind.ZOOM_SONG,
        key="opening_songs[0]",
    )

    assert (
        get_friday_zoom_media_key(block)
        == "opening_songs[0]"
    )

    assert (
        get_friday_zoom_media_type(block)
        == ZoomMediaType.VIDEO
    )


def test_first_prayer_uses_audio_key():
    block = WorshipBlock(
        kind=BlockKind.PRAYER_TOPICS,
        key="first_prayer",
    )

    assert (
        get_friday_zoom_media_key(block)
        == "first_prayer_audio"
    )

    assert (
        get_friday_zoom_media_type(block)
        == ZoomMediaType.AUDIO
    )


def test_pre_service_has_audio_key():
    block = WorshipBlock(
        kind=BlockKind.PRE_SERVICE,
        key="pre_service",
    )

    assert (
        get_friday_zoom_media_key(block)
        == "pre_service_audio"
    )

    assert (
        get_friday_zoom_media_type(block)
        == ZoomMediaType.AUDIO
    )


def test_non_media_block_returns_none():
    block = WorshipBlock(
        kind=BlockKind.SERMON_TITLE,
        key="sermon_title",
    )

    assert (
        get_friday_zoom_media_key(block)
        is None
    )

    assert (
        get_friday_zoom_media_type(block)
        is None
    )