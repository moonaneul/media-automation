import platform

import pytest

from media_automation.ppt import (
    PowerPointComMediaEmbedder,
    create_platform_media_embedder,
)

from pathlib import Path


def test_media_embedder_factory_on_current_platform():
    system = platform.system()

    if system == "Windows":
        embedder = (
            create_platform_media_embedder()
        )

        assert isinstance(
            embedder,
            PowerPointComMediaEmbedder,
        )

    elif system == "Darwin":
        with pytest.raises(
            RuntimeError,
            match="Windows 제작 환경",
        ):
            create_platform_media_embedder()

    else:
        with pytest.raises(
            RuntimeError,
            match="지원하지 않는 운영체제",
        ):
            create_platform_media_embedder()
class FakePlaySettings:
    def __init__(self):
        self.PlayOnEntry = None
        self.PauseAnimation = None
        self.LoopUntilStopped = None
        self.HideWhileNotPlaying = None


class FakeAnimationSettings:
    def __init__(self):
        self.PlaySettings = FakePlaySettings()


class FakeMediaShape:
    def __init__(self):
        self.AnimationSettings = (
            FakeAnimationSettings()
        )


class FakeShapes:
    def __init__(self):
        self.shape = FakeMediaShape()
        self.calls = []

    def AddMediaObject2(self, *args):
        self.calls.append(args)
        return self.shape


class FakeEffect:
    def __init__(self):
        self.moved_to = None

    def MoveTo(self, position):
        self.moved_to = position


class FakeMainSequence:
    def __init__(self):
        self.calls = []
        self.effect = FakeEffect()

    def AddEffect(self, *args):
        self.calls.append(args)
        return self.effect


class FakeTimeLine:
    def __init__(self):
        self.MainSequence = FakeMainSequence()


class FakeSlide:
    def __init__(self):
        self.Shapes = FakeShapes()
        self.TimeLine = FakeTimeLine()


class FakePageSetup:
    SlideWidth = 1280
    SlideHeight = 720


class FakePresentation:
    def __init__(self):
        self.PageSetup = FakePageSetup()


def test_video_uses_click_playback():
    embedder = PowerPointComMediaEmbedder()

    slide = FakeSlide()
    presentation = FakePresentation()

    embedder._embed_video(
        slide,
        Path("song.mp4"),
        presentation,
    )

    settings = (
        slide.Shapes.shape
        .AnimationSettings
        .PlaySettings
    )

    assert settings.PlayOnEntry is False
    assert settings.LoopUntilStopped is False


def test_audio_uses_autoplay_and_loop():
    embedder = PowerPointComMediaEmbedder()

    slide = FakeSlide()

    embedder._embed_audio(
        slide,
        Path("prayer.mp3"),
    )

    settings = (
        slide.Shapes.shape
        .AnimationSettings
        .PlaySettings
    )

    assert settings.PlayOnEntry is False
    assert settings.PauseAnimation is False
    assert settings.LoopUntilStopped is True
    assert settings.HideWhileNotPlaying is True

    sequence = slide.TimeLine.MainSequence

    assert sequence.calls == [
        (
            slide.Shapes.shape,
            83,
            0,
            2,
        )
    ]

    assert sequence.effect.moved_to == 1

