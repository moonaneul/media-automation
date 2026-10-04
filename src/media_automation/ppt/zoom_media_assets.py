from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


class ZoomMediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"


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
    key: str
    media_type: ZoomMediaType
    path: Path
    title: str | None = None


class ZoomMediaAssetProvider(Protocol):
    def get_media_asset(
        self,
        key: str,
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
        key: str,
    ) -> ZoomMediaAsset:
        asset = self._assets.get(key)

        if asset is None:
            raise MissingZoomMediaAssetError(
                "등록된 Zoom 미디어가 "
                f"없습니다: {key}"
            )

        if not asset.path.exists():
            raise MissingZoomMediaAssetError(
                "Zoom 미디어 파일이 "
                "존재하지 않습니다: "
                f"{key} -> {asset.path}"
            )

        if asset.path.stat().st_size == 0:
            raise InvalidZoomMediaAssetError(
                "Zoom 미디어 파일이 "
                f"비어 있습니다: {key}"
            )

        return asset