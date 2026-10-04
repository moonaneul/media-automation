from __future__ import annotations

import platform
from pathlib import Path
from typing import Protocol

from .zoom_media_assets import (
    ZoomMediaAsset,
    ZoomMediaType,
)


class MediaEmbedder(Protocol):
    def embed(
        self,
        presentation_path: str | Path,
        *,
        slide_number: int,
        asset: ZoomMediaAsset,
    ) -> None:
        ...


class PowerPointComMediaEmbedder:
    """
    Windows + Microsoft PowerPoint용
    MP4/MP3 삽입기.

    실제 재생 성공 여부는 별도 검수한다.
    """

    def _require_windows(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError(
                "PowerPoint COM 미디어 삽입은 "
                "Windows에서만 지원합니다."
            )

    def embed(
        self,
        presentation_path: str | Path,
        *,
        slide_number: int,
        asset: ZoomMediaAsset,
    ) -> None:
        self._require_windows()

        presentation_path = (
            Path(presentation_path).resolve()
        )
        media_path = asset.path.resolve()

        if slide_number < 1:
            raise ValueError(
                "slide_number는 1 이상이어야 합니다."
            )

        if not presentation_path.exists():
            raise FileNotFoundError(
                "대상 PPT가 없습니다: "
                f"{presentation_path}"
            )

        if not media_path.exists():
            raise FileNotFoundError(
                "미디어 파일이 없습니다: "
                f"{media_path}"
            )

        if media_path.stat().st_size == 0:
            raise RuntimeError(
                "미디어 파일이 비어 있습니다: "
                f"{media_path}"
            )

        try:
            import win32com.client
        except ImportError as error:
            raise RuntimeError(
                "Windows PowerPoint 미디어 삽입에는 "
                "pywin32가 필요합니다."
            ) from error

        powerpoint = None
        presentation = None

        try:
            powerpoint = (
                win32com.client.DispatchEx(
                    "PowerPoint.Application"
                )
            )

            presentation = (
                powerpoint.Presentations.Open(
                    str(presentation_path),
                    False,
                    False,
                    False,
                )
            )

            if slide_number > presentation.Slides.Count:
                raise ValueError(
                    "존재하지 않는 슬라이드 번호입니다: "
                    f"{slide_number}"
                )

            slide = presentation.Slides(
                slide_number
            )

            if (
                asset.media_type
                == ZoomMediaType.VIDEO
            ):
                self._embed_video(
                    slide,
                    media_path,
                    presentation,
                )

            elif (
                asset.media_type
                == ZoomMediaType.AUDIO
            ):
                self._embed_audio(
                    slide,
                    media_path,
                )

            else:
                raise ValueError(
                    "지원하지 않는 Zoom 미디어 "
                    f"유형입니다: {asset.media_type}"
                )

            presentation.Save()

        finally:
            if presentation is not None:
                presentation.Close()

            if powerpoint is not None:
                powerpoint.Quit()

    def _embed_video(
        self,
        slide,
        media_path: Path,
        presentation,
    ) -> None:
        width = presentation.PageSetup.SlideWidth
        height = presentation.PageSetup.SlideHeight

        slide.Shapes.AddMediaObject2(
            str(media_path),
            False,
            True,
            0,
            0,
            width,
            height,
        )

    def _embed_audio(
        self,
        slide,
        media_path: Path,
    ) -> None:
        # 화면 밖에 가까운 작은 크기로 배치.
        # 실제 예배 화면에서 아이콘이 눈에 띄지 않도록 한다.
        slide.Shapes.AddMediaObject2(
            str(media_path),
            False,
            True,
            0,
            0,
            1,
            1,
        )


def create_platform_media_embedder() -> MediaEmbedder:
    system = platform.system()

    if system == "Windows":
        return PowerPointComMediaEmbedder()

    if system == "Darwin":
        raise RuntimeError(
            "최종 MP4/MP3 삽입은 현재 "
            "Microsoft PowerPoint가 설치된 "
            "Windows 제작 환경에서만 지원합니다. "
            "Mac에서는 미디어 입력 검증까지만 "
            "지원합니다."
        )

    raise RuntimeError(
        f"지원하지 않는 운영체제입니다: {system}"
    )