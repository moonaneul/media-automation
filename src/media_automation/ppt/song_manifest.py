from __future__ import annotations

from pathlib import Path

import yaml

from .song_assets import (
    FileSongAssetProvider,
    SongAsset,
)


def load_song_asset_provider(
    manifest_path: str | Path,
) -> FileSongAssetProvider:
    manifest_path = Path(
        manifest_path
    )

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        raw = yaml.safe_load(
            file
        )

    if not isinstance(
        raw,
        dict,
    ):
        raise ValueError(
            "찬양 manifest의 최상위 값은 "
            "객체여야 합니다."
        )

    songs = raw.get(
        "songs"
    )

    if not isinstance(
        songs,
        dict,
    ):
        raise ValueError(
            "찬양 manifest에 songs 객체가 "
            "필요합니다."
        )

    base_dir = (
        manifest_path.parent
    )

    assets: dict[
        str,
        Path | SongAsset,
    ] = {}

    for title, value in songs.items():
        if not isinstance(
            title,
            str,
        ):
            raise ValueError(
                "찬양 제목은 문자열이어야 합니다."
            )

        if isinstance(
            value,
            str,
        ):
            path = Path(
                value
            )

            if not path.is_absolute():
                path = (
                    base_dir
                    / path
                )

            assets[
                title
            ] = path

            continue

        if not isinstance(
            value,
            dict,
        ):
            raise ValueError(
                f"{title}의 manifest 형식이 "
                "잘못되었습니다."
            )

        path_raw = value.get(
            "path"
        )

        if not isinstance(
            path_raw,
            str,
        ):
            raise ValueError(
                f"{title}에 path가 필요합니다."
            )

        path = Path(
            path_raw
        )

        if not path.is_absolute():
            path = (
                base_dir
                / path
            )

        slides = value.get(
            "slides"
        )

        if slides is None:
            assets[
                title
            ] = SongAsset(
                title=title,
                path=path,
            )

            continue

        if (
            not isinstance(
                slides,
                list,
            )
            or len(slides) != 2
        ):
            raise ValueError(
                f"{title}의 slides는 "
                "[start, end] 형식이어야 합니다."
            )

        start_slide, end_slide = slides

        if (
            not isinstance(
                start_slide,
                int,
            )
            or not isinstance(
                end_slide,
                int,
            )
        ):
            raise ValueError(
                f"{title}의 slides 값은 "
                "정수여야 합니다."
            )

        assets[
            title
        ] = SongAsset(
            title=title,
            path=path,
            start_slide=start_slide,
            end_slide=end_slide,
        )

    return FileSongAssetProvider(
        assets
    )