from __future__ import annotations

import argparse
import platform
import zipfile
from pathlib import Path

from media_automation.ppt.base import (
    add_blank_slide,
    create_16x9_presentation,
)
from media_automation.ppt import (
    MediaEmbedRequest,
    ZoomMediaAsset,
    ZoomMediaType,
    create_platform_media_embedder,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Windows PowerPoint MP4/MP3 "
            "실제 삽입 smoke test"
        )
    )

    parser.add_argument(
        "--video",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--audio",
        type=Path,
        required=True,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "output/windows_media_smoke.pptx"
        ),
    )

    args = parser.parse_args()

    if platform.system() != "Windows":
        raise RuntimeError(
            "이 smoke test는 Microsoft PowerPoint가 "
            "설치된 Windows에서 실행해야 합니다."
        )

    for name, path in {
        "video": args.video,
        "audio": args.audio,
    }.items():
        if not path.exists():
            raise FileNotFoundError(
                f"{name} 파일이 없습니다: {path}"
            )

        if path.stat().st_size == 0:
            raise RuntimeError(
                f"{name} 파일이 비어 있습니다: {path}"
            )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    #
    # 1. 미디어 없는 16:9 PPT 생성
    #
    prs = create_16x9_presentation()

    add_blank_slide(prs)
    add_blank_slide(prs)

    prs.save(args.output)

    #
    # 2. 실제 PowerPoint COM으로 삽입
    #
    video = ZoomMediaAsset(
        key="smoke_video",
        media_type=ZoomMediaType.VIDEO,
        path=args.video,
    )

    audio = ZoomMediaAsset(
        key="smoke_audio",
        media_type=ZoomMediaType.AUDIO,
        path=args.audio,
    )

    embedder = (
        create_platform_media_embedder()
    )

    embedder.embed_many(
        args.output,
        requests=[
            MediaEmbedRequest(
                slide_number=1,
                asset=video,
            ),
            MediaEmbedRequest(
                slide_number=2,
                asset=audio,
            ),
        ],
    )

    #
    # 3. PPTX 패키지에 실제 미디어가 들어갔는지 확인
    #
    with zipfile.ZipFile(
        args.output
    ) as archive:
        media_files = sorted(
            name
            for name
            in archive.namelist()
            if name.startswith(
                "ppt/media/"
            )
        )

    print()
    print(
        "=== Windows Media Smoke Test ==="
    )
    print(
        f"output : {args.output.resolve()}"
    )

    print()
    print(
        f"embedded media files: "
        f"{len(media_files)}"
    )

    for media_file in media_files:
        print(
            f"- {media_file}"
        )

    print()
    print(
        "PowerPoint COM 삽입 완료."
    )
    print()
    print(
        "이제 PowerPoint에서 직접 확인:"
    )
    print(
        "1. 슬라이드 1: 영상이 자동 시작하지 않아야 함"
    )
    print(
        "2. 슬라이드 1: 클릭하면 영상이 재생되어야 함"
    )
    print(
        "3. 슬라이드 2: 진입 즉시 음원이 재생되어야 함"
    )
    print(
        "4. 슬라이드 2: 음원이 반복 재생되어야 함"
    )
    print(
        "5. 슬라이드 2: 음원 아이콘이 "
        "슬라이드 쇼에서 보이지 않아야 함"
    )


if __name__ == "__main__":
    main()