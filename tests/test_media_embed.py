import platform

import pytest

from media_automation.ppt import (
    PowerPointComMediaEmbedder,
    create_platform_media_embedder,
)


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