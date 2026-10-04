from __future__ import annotations

from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)

from .zoom_media_assets import (
    ZoomMediaType,
)


FRIDAY_ZOOM_AUDIO_KEYS = {
    "pre_service": "pre_service_audio",
    "first_prayer": "first_prayer_audio",
    "word_prayer": "word_prayer_audio",
    "community_prayer": "community_prayer_audio",
    "personal_prayer": "personal_prayer_audio",
}


def get_friday_zoom_media_key(
    block: WorshipBlock,
) -> str | None:
    if block.kind == BlockKind.ZOOM_SONG:
        return block.key

    return FRIDAY_ZOOM_AUDIO_KEYS.get(
        block.key
    )


def get_friday_zoom_media_type(
    block: WorshipBlock,
) -> ZoomMediaType | None:
    if block.kind == BlockKind.ZOOM_SONG:
        return ZoomMediaType.VIDEO

    if block.key in FRIDAY_ZOOM_AUDIO_KEYS:
        return ZoomMediaType.AUDIO

    return None