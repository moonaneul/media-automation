from __future__ import annotations

import platform
from pathlib import Path
from typing import Protocol

from pptx import Presentation


class SlideMerger(Protocol):
    def insert_all(
        self,
        destination: str | Path,
        source: str | Path,
        *,
        after_slide: int,
    ) -> None:
        ...

    def insert_range(
        self,
        destination: str | Path,
        source: str | Path,
        *,
        after_slide: int,
        start_slide: int,
        end_slide: int,
    ) -> None:
        ...


class PowerPointComSlideMerger:
    """
    Microsoft PowerPoint COM을 이용해
    원본 슬라이드를 디자인 그대로 삽입한다.

    실제 COM 병합은 Windows + PowerPoint 환경에서만 가능하다.
    Mac에서도 모듈 import 자체는 가능해야 한다.
    """

    def _require_windows(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError(
                "PowerPoint COM 슬라이드 병합은 "
                "현재 Windows + Microsoft PowerPoint "
                "환경에서만 지원합니다."
            )

    def insert_all(
        self,
        destination: str | Path,
        source: str | Path,
        *,
        after_slide: int,
    ) -> None:
        source = Path(source)

        source_prs = Presentation(
            source
        )

        slide_count = len(
            source_prs.slides
        )

        if slide_count == 0:
            return

        self.insert_range(
            destination,
            source,
            after_slide=after_slide,
            start_slide=1,
            end_slide=slide_count,
        )

    def insert_range(
        self,
        destination: str | Path,
        source: str | Path,
        *,
        after_slide: int,
        start_slide: int,
        end_slide: int,
    ) -> None:
        self._require_windows()

        destination = Path(
            destination
        ).resolve()

        source = Path(
            source
        ).resolve()

        if not destination.exists():
            raise FileNotFoundError(
                f"대상 PPT가 없습니다: "
                f"{destination}"
            )

        if not source.exists():
            raise FileNotFoundError(
                f"삽입할 PPT가 없습니다: "
                f"{source}"
            )

        if start_slide < 1:
            raise ValueError(
                "start_slide은 1 이상이어야 합니다."
            )

        if end_slide < start_slide:
            raise ValueError(
                "end_slide은 start_slide보다 "
                "작을 수 없습니다."
            )

        try:
            import win32com.client
        except ImportError as error:
            raise RuntimeError(
                "PowerPoint COM 병합을 사용하려면 "
                "Windows에서 pywin32가 필요합니다."
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
                    str(destination),
                    False,
                    False,
                    False,
                )
            )

            presentation.Slides.InsertFromFile(
                str(source),
                after_slide,
                start_slide,
                end_slide,
            )

            presentation.Save()

        finally:
            if presentation is not None:
                presentation.Close()

            if powerpoint is not None:
                powerpoint.Quit()