from __future__ import annotations

from pathlib import Path

from media_automation.bible import BibleProvider
from media_automation.planning import WorshipBlock

from .assets import PreServiceSlideProvider
from .in_person_structure import (
    InPersonSlideRange,
    InPersonStructureResult,
    build_in_person_structure,
)
from .song_assets import SongAssetProvider


WednesdaySlideRange = InPersonSlideRange
WednesdayStructureResult = InPersonStructureResult


def build_wednesday_structure(
    plan: list[WorshipBlock],
    output_path: str | Path,
    *,
    bible_provider: BibleProvider,
    pre_service_provider: PreServiceSlideProvider,
    song_asset_provider: SongAssetProvider,
    skip_missing_songs: bool = True,
) -> WednesdayStructureResult:
    return build_in_person_structure(
        plan,
        output_path,
        bible_provider=bible_provider,
        pre_service_provider=pre_service_provider,
        song_asset_provider=song_asset_provider,
        skip_missing_songs=skip_missing_songs,
    )