from __future__ import annotations

from pathlib import Path

import yaml

from .zoom_media_assets import (
    FileZoomMediaAssetProvider,
    ZoomMediaAsset,
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

    for title, value in media.items():
        if not isinstance(title, str):
            raise ValueError(
                "Zoom 찬양 제목은 "
                "문자열이어야 합니다."
            )

        if not isinstance(value, dict):
            raise ValueError(
                f"{title}의 media manifest "
                "형식이 잘못되었습니다."
            )

        video_raw = value.get("video")

        if not isinstance(
            video_raw,
            str,
        ):
            raise ValueError(
                f"{title}에 video가 "
                "필요합니다."
            )

        video_path = Path(
            video_raw
        )

        if not video_path.is_absolute():
            video_path = (
                base_dir / video_path
            )

        audio_raw = value.get(
            "audio"
        )

        audio_path = None

        if audio_raw is not None:
            if not isinstance(
                audio_raw,
                str,
            ):
                raise ValueError(
                    f"{title}의 audio는 "
                    "문자열이어야 합니다."
                )

            audio_path = Path(
                audio_raw
            )

            if not audio_path.is_absolute():
                audio_path = (
                    base_dir
                    / audio_path
                )

        assets[title] = ZoomMediaAsset(
            title=title,
            video_path=video_path,
            audio_path=audio_path,
        )

    return FileZoomMediaAssetProvider(
        assets
    )