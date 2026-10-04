from __future__ import annotations

from pathlib import Path

import yaml

from .zoom_media_assets import (
    FileZoomMediaAssetProvider,
    ZoomMediaAsset,
    ZoomMediaType,
)


def load_zoom_media_asset_provider(
    manifest_path: str | Path,
) -> FileZoomMediaAssetProvider:
    manifest_path = Path(
        manifest_path
    )

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(
            "Zoom media manifest의 "
            "최상위 값은 객체여야 합니다."
        )

    media = raw.get("media")

    if not isinstance(media, dict):
        raise ValueError(
            "Zoom media manifest에 "
            "media 객체가 필요합니다."
        )

    base_dir = manifest_path.parent

    assets: dict[
        str,
        ZoomMediaAsset,
    ] = {}

    for key, value in media.items():
        if not isinstance(key, str):
            raise ValueError(
                "Zoom media key는 "
                "문자열이어야 합니다."
            )

        if not isinstance(value, dict):
            raise ValueError(
                f"{key}의 media manifest "
                "형식이 잘못되었습니다."
            )

        type_raw = value.get("type")
        path_raw = value.get("path")
        title = value.get("title")

        try:
            media_type = ZoomMediaType(
                type_raw
            )
        except ValueError as error:
            raise ValueError(
                f"{key}의 type은 "
                "video 또는 audio여야 합니다."
            ) from error

        if not isinstance(path_raw, str):
            raise ValueError(
                f"{key}에 path가 필요합니다."
            )

        if (
            title is not None
            and not isinstance(title, str)
        ):
            raise ValueError(
                f"{key}의 title은 "
                "문자열이어야 합니다."
            )

        path = Path(path_raw)

        if not path.is_absolute():
            path = base_dir / path

        assets[key] = ZoomMediaAsset(
            key=key,
            media_type=media_type,
            path=path,
            title=title,
        )

    return FileZoomMediaAssetProvider(
        assets
    )