from pathlib import Path

import pytest

from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)
from media_automation.ppt import (
    FridayZoomSlideRange,
    InvalidZoomMediaAssetError,
    ZoomMediaAsset,
    ZoomMediaType,
    plan_friday_zoom_media_placements,
)


class FakeMediaProvider:
    def __init__(
        self,
        assets: dict[str, ZoomMediaAsset],
    ):
        self.assets = assets

    def get_media_asset(
        self,
        key: str,
    ) -> ZoomMediaAsset:
        return self.assets[key]


def test_media_placements_map_blocks_to_slides():
    plan = [
        WorshipBlock(
            kind=BlockKind.PRE_SERVICE,
            key="pre_service",
        ),
        WorshipBlock(
            kind=BlockKind.ZOOM_SONG,
            key="opening_songs[0]",
        ),
        WorshipBlock(
            kind=BlockKind.PRAYER_TOPICS,
            key="first_prayer",
        ),
        WorshipBlock(
            kind=BlockKind.SCRIPTURE,
            key="scripture",
        ),
    ]

    ranges = {
        "pre_service": (
            FridayZoomSlideRange(1, 1)
        ),
        "opening_songs[0]": (
            FridayZoomSlideRange(2, 2)
        ),
        "first_prayer": (
            FridayZoomSlideRange(3, 3)
        ),
        "scripture": (
            FridayZoomSlideRange(4, 9)
        ),
    }

    provider = FakeMediaProvider(
        {
            "opening_songs[0]": (
                ZoomMediaAsset(
                    key="opening_songs[0]",
                    media_type=(
                        ZoomMediaType.VIDEO
                    ),
                    path=Path("song.mp4"),
                )
            ),
            "first_prayer_audio": (
                ZoomMediaAsset(
                    key="first_prayer_audio",
                    media_type=(
                        ZoomMediaType.AUDIO
                    ),
                    path=Path("prayer.mp3"),
                )
            ),
        }
    )

    placements = (
        plan_friday_zoom_media_placements(
            plan,
            ranges,
            provider,
        )
    )

    assert len(placements) == 2

    assert (
        placements[0].block_key
        == "opening_songs[0]"
    )
    assert placements[0].slide_number == 2
    assert (
        placements[0].media_key
        == "opening_songs[0]"
    )

    assert (
        placements[1].block_key
        == "first_prayer"
    )
    assert placements[1].slide_number == 3
    assert (
        placements[1].media_key
        == "first_prayer_audio"
    )


def test_pre_service_audio_is_excluded_by_default():
    plan = [
        WorshipBlock(
            kind=BlockKind.PRE_SERVICE,
            key="pre_service",
        ),
    ]

    ranges = {
        "pre_service": (
            FridayZoomSlideRange(1, 1)
        ),
    }

    provider = FakeMediaProvider({})

    placements = (
        plan_friday_zoom_media_placements(
            plan,
            ranges,
            provider,
        )
    )

    assert placements == []


def test_media_type_mismatch_is_rejected():
    plan = [
        WorshipBlock(
            kind=BlockKind.ZOOM_SONG,
            key="opening_songs[0]",
        ),
    ]

    ranges = {
        "opening_songs[0]": (
            FridayZoomSlideRange(2, 2)
        ),
    }

    provider = FakeMediaProvider(
        {
            "opening_songs[0]": (
                ZoomMediaAsset(
                    key="opening_songs[0]",
                    media_type=(
                        ZoomMediaType.AUDIO
                    ),
                    path=Path("wrong.mp3"),
                )
            ),
        }
    )

    with pytest.raises(
        InvalidZoomMediaAssetError,
    ):
        plan_friday_zoom_media_placements(
            plan,
            ranges,
            provider,
        )