from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class MissingZoomMediaAssetError(
    LookupError
):
    pass


class InvalidZoomMediaAssetError(
    RuntimeError
):
    pass


@dataclass(frozen=True, slots=True)
class ZoomMediaAsset:
    title: str
    video_path: Path
    audio_path: Path | None = None


class ZoomMediaAssetProvider(Protocol):
    def get_media_asset(
        self,
        title: str,
    ) -> ZoomMediaAsset:
        ...


class FileZoomMediaAssetProvider:
    def __init__(
        self,
        assets: dict[
            str,
            ZoomMediaAsset,
        ],
    ) -> None:
        self._assets = dict(assets)

    def get_media_asset(
        self,
        title: str,
    ) -> ZoomMediaAsset:
        asset = self._assets.get(title)

        if asset is None:
            raise MissingZoomMediaAssetError(
                "등록된 Zoom 찬양 미디어가 "
                f"없습니다: {title}"
            )

        if not asset.video_path.exists():
            raise MissingZoomMediaAssetError(
                "Zoom 찬양 영상 파일이 "
                "존재하지 않습니다: "
                f"{title} -> "
                f"{asset.video_path}"
            )

        if asset.video_path.stat().st_size == 0:
            raise InvalidZoomMediaAssetError(
                "Zoom 찬양 영상 파일이 "
                f"비어 있습니다: {title}"
            )

        if asset.audio_path is not None:
            if not asset.audio_path.exists():
                raise MissingZoomMediaAssetError(
                    "Zoom 찬양 음원 파일이 "
                    "존재하지 않습니다: "
                    f"{title} -> "
                    f"{asset.audio_path}"
                )

            if (
                asset.audio_path.stat().st_size
                == 0
            ):
                raise InvalidZoomMediaAssetError(
                    "Zoom 찬양 음원 파일이 "
                    f"비어 있습니다: {title}"
                )

        return asset