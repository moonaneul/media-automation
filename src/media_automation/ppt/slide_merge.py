from __future__ import annotations

import platform
import subprocess
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
    Windows + Microsoft PowerPoint용 슬라이드 병합기.
    """

    def _require_windows(self) -> None:
        if platform.system() != "Windows":
            raise RuntimeError(
                "PowerPoint COM 슬라이드 병합은 "
                "Windows에서만 지원합니다."
            )

    def insert_all(
        self,
        destination: str | Path,
        source: str | Path,
        *,
        after_slide: int,
    ) -> None:
        source = Path(source)

        source_prs = Presentation(source)
        slide_count = len(source_prs.slides)

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

        destination = Path(destination).resolve()
        source = Path(source).resolve()

        if start_slide < 1:
            raise ValueError(
                "start_slide은 1 이상이어야 합니다."
            )

        if end_slide < start_slide:
            raise ValueError(
                "end_slide은 start_slide보다 "
                "작을 수 없습니다."
            )

        if not destination.exists():
            raise FileNotFoundError(
                f"대상 PPT가 없습니다: {destination}"
            )

        if not source.exists():
            raise FileNotFoundError(
                f"삽입할 PPT가 없습니다: {source}"
            )

        try:
            import win32com.client
        except ImportError as error:
            raise RuntimeError(
                "Windows PowerPoint 병합에는 "
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


class MacPowerPointAppleScriptSlideMerger:
    """
    macOS + Microsoft PowerPoint용 슬라이드 병합기.

    PowerPoint 자체의 copy 기능과 macOS의 실제 Command+V UI 입력을
    함께 사용해서 원본 악보 슬라이드를 재구성하지 않고 복사한다.
    """

    def _require_macos(self) -> None:
        if platform.system() != "Darwin":
            raise RuntimeError(
                "Mac PowerPoint 슬라이드 병합은 "
                "macOS에서만 지원합니다."
            )

    def insert_all(
        self,
        destination: str | Path,
        source: str | Path,
        *,
        after_slide: int,
    ) -> None:
        source = Path(source)

        source_prs = Presentation(source)
        slide_count = len(source_prs.slides)

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
        self._require_macos()

        destination = Path(destination).resolve()
        source = Path(source).resolve()

        if start_slide < 1:
            raise ValueError(
                "start_slide은 1 이상이어야 합니다."
            )

        if end_slide < start_slide:
            raise ValueError(
                "end_slide은 start_slide보다 "
                "작을 수 없습니다."
            )

        if after_slide < 1:
            raise ValueError(
                "Mac PowerPoint 병합은 현재 "
                "첫 슬라이드 앞 삽입을 지원하지 않습니다."
            )

        if not destination.exists():
            raise FileNotFoundError(
                f"대상 PPT가 없습니다: {destination}"
            )

        if not source.exists():
            raise FileNotFoundError(
                f"삽입할 PPT가 없습니다: {source}"
            )

        # PowerPoint for Mac의 `paste object view ...`가 일부 버전에서
        # 전체 슬라이드를 실제 슬라이드로 삽입하지 않는 사례가 있다.
        # source slide는 PowerPoint 자체 copy 명령으로 복사하고,
        # destination document window를 전면 선택한 뒤 실제 Command+V를
        # System Events로 보내는 방식으로 우회한다.
        script = r'''
on run argv
    set destinationPath to item 1 of argv
    set sourcePath to item 2 of argv
    set afterSlideNumber to (item 3 of argv) as integer
    set startSlideNumber to (item 4 of argv) as integer
    set endSlideNumber to (item 5 of argv) as integer
    set destinationName to item 6 of argv
    set sourceName to item 7 of argv

    set destinationFile to POSIX file destinationPath as alias
    set sourceFile to POSIX file sourcePath as alias

    tell application "Microsoft PowerPoint"
        activate

        open sourceFile
        delay 0.5
        open destinationFile
        delay 0.5

        set sourcePresentation to presentation sourceName
        set destinationPresentation to presentation destinationName
        set destinationWindow to document window 1 of destinationPresentation

        select destinationWindow
        set view type of destinationWindow to slide sorter view
        delay 0.3

        set insertionPoint to afterSlideNumber

        repeat with sourceSlideNumber from startSlideNumber to endSlideNumber
            set beforeCount to count slides of destinationPresentation

            copy object slide sourceSlideNumber of sourcePresentation
            delay 0.2

            select destinationWindow
            select slide insertionPoint of destinationPresentation
            delay 0.2

            tell application "System Events"
                tell process "Microsoft PowerPoint"
                    set frontmost to true
                    keystroke "v" using command down
                end tell
            end tell

            delay 0.5

            set afterCount to count slides of destinationPresentation
            if afterCount is not (beforeCount + 1) then
                error "Command+V 후 대상 PPT의 슬라이드 수가 증가하지 않았습니다."
            end if

            set insertionPoint to insertionPoint + 1
        end repeat

        set view type of destinationWindow to normal view

        close sourcePresentation saving no
        close destinationPresentation saving yes
    end tell
end run
'''

        result = subprocess.run(
            [
                "osascript",
                "-e",
                script,
                str(destination),
                str(source),
                str(after_slide),
                str(start_slide),
                str(end_slide),
                destination.name,
                source.name,
            ],
            text=True,
            capture_output=True,
        )

        if result.returncode != 0:
            message = (
                result.stderr.strip()
                or result.stdout.strip()
                or "알 수 없는 AppleScript 오류"
            )

            if (
                "not allowed to send keystrokes" in message.lower()
                or "보조 접근" in message
                or "accessibility" in message.lower()
            ):
                message += (
                    " | 시스템 설정 > 개인정보 보호 및 보안 > "
                    "손쉬운 사용에서 Terminal의 제어 권한을 허용해주세요."
                )

            raise RuntimeError(
                "Mac PowerPoint 슬라이드 병합에 "
                f"실패했습니다: {message}"
            )


def create_platform_slide_merger() -> SlideMerger:
    system = platform.system()

    if system == "Windows":
        return PowerPointComSlideMerger()

    if system == "Darwin":
        return MacPowerPointAppleScriptSlideMerger()

    raise RuntimeError(
        f"지원하지 않는 운영체제입니다: {system}"
    )
