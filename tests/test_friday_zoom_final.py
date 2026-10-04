from pathlib import Path

from media_automation.bible import (
    InMemoryBibleProvider,
)
from media_automation.planning import (
    BlockKind,
    WorshipBlock,
)
from media_automation.ppt import (
    ZoomMediaAsset,
    ZoomMediaType,
    build_friday_zoom_with_media,
)
from media_automation.weekly_data.models import (
    TopicsField,
    WeeklyStatus,
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


class FakeMediaEmbedder:
    def __init__(self):
        self.calls = []

    def embed_many(
        self,
        presentation_path,
        *,
        requests,
    ):
        self.calls.append(
            (
                Path(presentation_path),
                list(requests),
            )
        )


def test_final_builder_embeds_media_on_generated_slides(
    tmp_path,
):
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
            value=TopicsField(
                status=WeeklyStatus.VALUE,
                topics=[
                    "기도 제목",
                ],
            ),
        ),
    ]

    video = ZoomMediaAsset(
        key="opening_songs[0]",
        media_type=ZoomMediaType.VIDEO,
        path=Path("song.mp4"),
    )

    audio = ZoomMediaAsset(
        key="first_prayer_audio",
        media_type=ZoomMediaType.AUDIO,
        path=Path("prayer.mp3"),
    )

    provider = FakeMediaProvider(
        {
            "opening_songs[0]": video,
            "first_prayer_audio": audio,
        }
    )

    embedder = FakeMediaEmbedder()

    output = tmp_path / "friday.pptx"

    result = build_friday_zoom_with_media(
        plan,
        output,
        bible_provider=(
            InMemoryBibleProvider({})
        ),
        media_provider=provider,
        media_embedder=embedder,
    )

    assert output.exists()

    assert (
        result.slide_ranges[
            "pre_service"
        ].start
        == 1
    )

    assert (
        result.slide_ranges[
            "opening_songs[0]"
        ].start
        == 2
    )

    assert (
        result.slide_ranges[
            "first_prayer"
        ].start
        == 3
    )

    assert len(
        result.media_placements
    ) == 2

    assert len(embedder.calls) == 1

    presentation_path, requests = (
        embedder.calls[0]
    )

    assert presentation_path == output

    assert len(requests) == 2

    assert requests[0].slide_number == 2
    assert requests[0].asset is video

    assert requests[1].slide_number == 3
    assert requests[1].asset is audio