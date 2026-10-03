from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class MissingSongAssetError(
    LookupError
):
    pass


@dataclass(frozen=True, slots=True)
class SongAsset:
    title: str
    path: Path
    start_slide: int | None = None
    end_slide: int | None = None

    def __post_init__(self):
        has_start = (
            self.start_slide is not None
        )
        has_end = (
            self.end_slide is not None
        )

        if has_start != has_end:
            raise ValueError(
                "start_slide과 end_slide은 "
                "둘 다 지정하거나 둘 다 생략해야 합니다."
            )

        if self.start_slide is None:
            return

        if self.start_slide < 1:
            raise ValueError(
                "start_slide은 1 이상이어야 합니다."
            )

        if self.end_slide < self.start_slide:
            raise ValueError(
                "end_slide은 start_slide보다 "
                "작을 수 없습니다."
            )


class SongAssetProvider(Protocol):
    def get_song_asset(
        self,
        title: str,
    ) -> SongAsset:
        ...


class FileSongAssetProvider:
    def __init__(
        self,
        assets: dict[
            str,
            Path | SongAsset,
        ],
    ) -> None:
        self._assets: dict[
            str,
            SongAsset,
        ] = {}

        for title, asset in assets.items():
            if isinstance(
                asset,
                SongAsset,
            ):
                resolved = asset
            else:
                resolved = SongAsset(
                    title=title,
                    path=Path(asset),
                )

            self._assets[
                title
            ] = resolved

    def get_song_asset(
        self,
        title: str,
    ) -> SongAsset:
        asset = self._assets.get(
            title
        )

        if asset is None:
            raise MissingSongAssetError(
                f"등록된 악보 PPT가 없습니다: "
                f"{title}"
            )

        if not asset.path.exists():
            raise MissingSongAssetError(
                f"악보 PPT 파일이 존재하지 않습니다: "
                f"{title} -> {asset.path}"
            )

        return asset