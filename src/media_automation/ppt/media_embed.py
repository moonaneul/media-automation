from __future__ import annotations

import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence

from .zoom_media_assets import (
    ZoomMediaAsset,
    ZoomMediaType,
)


@dataclass(frozen=True, slots=True)
class MediaEmbedRequest:
    slide_number: int
    asset: ZoomMediaAsset


class MediaEmbedder(Protocol):
    def embed_many(
        self,
        presentation_path: str | Path,
        *,
        requests: Sequence[MediaEmbedRequest],
    ) -> None:
        ...


class PowerPointComMediaEmbedder:
    """
    Windows + Microsoft PowerPoint용
    MP4/MP3 삽입기.

    하나의 PowerPoint 세션에서
    여러 미디어를 삽입하고 한 번 저장한다.

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
        """
        단일 삽입 호환용 메서드.
        내부적으로 embed_many를 사용한다.
        """

        self.embed_many(
            presentation_path,
            requests=[
                MediaEmbedRequest(
                    slide_number=slide_number,
                    asset=asset,
                )
            ],
        )

    def embed_many(
        self,
        presentation_path: str | Path,
        *,
        requests: Sequence[MediaEmbedRequest],
    ) -> None:
        self._require_windows()

        presentation_path = (
            Path(presentation_path).resolve()
        )

        if not presentation_path.exists():
            raise FileNotFoundError(
                "대상 PPT가 없습니다: "
                f"{presentation_path}"
            )

        if not requests:
            return

        resolved_requests: list[
            tuple[
                MediaEmbedRequest,
                Path,
            ]
        ] = []

        for request in requests:
            if request.slide_number < 1:
                raise ValueError(
                    "slide_number는 "
                    "1 이상이어야 합니다."
                )

            media_path = (
                request.asset.path.resolve()
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

            resolved_requests.append(
                (
                    request,
                    media_path,
                )
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

            for (
                request,
                media_path,
            ) in resolved_requests:
                if (
                    request.slide_number
                    > presentation.Slides.Count
                ):
                    raise ValueError(
                        "존재하지 않는 슬라이드 "
                        "번호입니다: "
                        f"{request.slide_number}"
                    )

                slide = presentation.Slides(
                    request.slide_number
                )

                asset = request.asset

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
                        "유형입니다: "
                        f"{asset.media_type}"
                    )

            # 모든 삽입이 끝난 뒤 한 번만 저장
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
        width = (
            presentation.PageSetup.SlideWidth
        )
        height = (
            presentation.PageSetup.SlideHeight
        )

        shape = slide.Shapes.AddMediaObject2(
            str(media_path),
            False,
            True,
            0,
            0,
            width,
            height,
        )

        play_settings = (
            shape.AnimationSettings.PlaySettings
        )

        # 과거 금요 Zoom PPT 기준:
        # 영상은 자동재생하지 않고 클릭 재생한다.
        play_settings.PlayOnEntry = False
        play_settings.LoopUntilStopped = False


    def _embed_audio(
        self,
        slide,
        media_path: Path,
    ) -> None:
        shape = slide.Shapes.AddMediaObject2(
            str(media_path),
            False,
            True,
            0,
            0,
            1,
            1,
        )

        play_settings = (
            shape.AnimationSettings.PlaySettings
        )

        # 과거 금요 Zoom PPT 기준:
        # 기도 음원은 슬라이드 진입 시 자동재생하고
        # 슬라이드가 유지되는 동안 반복한다.
        play_settings.PlayOnEntry = True
        play_settings.PauseAnimation = False
        play_settings.LoopUntilStopped = True

        # 예배 화면에서 음원 아이콘을 노출하지 않는다.
        play_settings.HideWhileNotPlaying = True


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