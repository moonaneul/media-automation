from __future__ import annotations

import argparse
import hashlib
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree


MEDIA_EXTENSIONS = {
    ".mp4",
    ".mp3",
    ".m4a",
    ".wav",
}


def slide_number_from_path(
    path: str,
) -> int | None:
    match = re.search(
        r"slide(\d+)\.xml\.rels$",
        path,
    )

    if match is None:
        return None

    return int(match.group(1))


def normalize_media_target(
    rels_path: str,
    target: str,
) -> str:
    slide_dir = posixpath.dirname(
        posixpath.dirname(rels_path)
    )

    return posixpath.normpath(
        posixpath.join(
            slide_dir,
            target,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "PPTX 내부 MP4/MP3 인벤토리와 "
            "ZIP 무결성을 검사합니다."
        )
    )

    parser.add_argument(
        "pptx",
        type=Path,
        help="검사할 PPTX",
    )

    parser.add_argument(
        "--extract-dir",
        type=Path,
        help=(
            "정상 미디어만 복사할 임시 폴더. "
            "지정하지 않으면 추출하지 않습니다."
        ),
    )

    args = parser.parse_args()

    if not args.pptx.exists():
        raise FileNotFoundError(
            f"PPTX를 찾을 수 없습니다: "
            f"{args.pptx}"
        )

    if args.extract_dir is not None:
        args.extract_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    with zipfile.ZipFile(
        args.pptx,
        "r",
    ) as archive:
        media_names = sorted(
            name
            for name in archive.namelist()
            if (
                name.startswith("ppt/media/")
                and Path(name).suffix.lower()
                in MEDIA_EXTENSIONS
            )
        )

        status_by_media: dict[
            str,
            tuple[str, int, str | None],
        ] = {}

        for name in media_names:
            info = archive.getinfo(name)

            try:
                data = archive.read(name)

            except zipfile.BadZipFile:
                status_by_media[name] = (
                    "CRC_ERROR",
                    info.file_size,
                    None,
                )
                continue

            digest = hashlib.sha256(
                data
            ).hexdigest()

            status_by_media[name] = (
                "OK",
                len(data),
                digest,
            )

            if args.extract_dir is not None:
                output = (
                    args.extract_dir
                    / Path(name).name
                )

                output.write_bytes(data)

        # -------------------------
        # 슬라이드 -> 미디어 관계
        # -------------------------

        slide_media: dict[
            int,
            list[str],
        ] = {}

        relationship_paths = sorted(
            name
            for name in archive.namelist()
            if (
                name.startswith(
                    "ppt/slides/_rels/"
                )
                and name.endswith(
                    ".xml.rels"
                )
            )
        )

        for rels_path in relationship_paths:
            slide_number = (
                slide_number_from_path(
                    rels_path
                )
            )

            if slide_number is None:
                continue

            xml = archive.read(
                rels_path
            )

            root = ElementTree.fromstring(
                xml
            )

            for relationship in root:
                target = relationship.get(
                    "Target"
                )

                if target is None:
                    continue

                suffix = Path(
                    target
                ).suffix.lower()

                if suffix not in MEDIA_EXTENSIONS:
                    continue

                media_path = (
                    normalize_media_target(
                        rels_path,
                        target,
                    )
                )

                media_list = slide_media.setdefault(
                    slide_number,
                    [],
                )

                if media_path not in media_list:
                    media_list.append(
                        media_path
                    )

    print()
    print("=== PPT Media Inventory ===")
    print(f"source : {args.pptx}")
    print(
        f"media files : "
        f"{len(media_names)}"
    )

    print()
    print("=== Media Files ===")

    for name in media_names:
        status, size, digest = (
            status_by_media[name]
        )

        print()
        print(f"- {name}")
        print(f"  status : {status}")
        print(f"  size   : {size}")

        if digest is not None:
            print(
                "  sha256 : "
                f"{digest[:16]}..."
            )

    print()
    print("=== Slide -> Media ===")

    if not slide_media:
        print(
            "직접 연결된 미디어 관계를 "
            "찾지 못했습니다."
        )

    for slide_number in sorted(
        slide_media
    ):
        print(
            f"slide {slide_number}:"
        )

        for media_path in (
            slide_media[slide_number]
        ):
            status = status_by_media.get(
                media_path,
                ("UNKNOWN", 0, None),
            )[0]

            print(
                f"  - {media_path} "
                f"[{status}]"
            )

    bad_media = [
        name
        for name, result
        in status_by_media.items()
        if result[0] != "OK"
    ]

    print()
    print("=== Result ===")
    print(
        f"OK      : "
        f"{len(media_names) - len(bad_media)}"
    )
    print(
        f"BAD     : {len(bad_media)}"
    )

    if bad_media:
        print()
        print(
            "주의: 파일이 PPT 안에 존재하지만 "
            "무결성 검사를 통과하지 못한 "
            "미디어가 있습니다."
        )

        for name in bad_media:
            print(f"- {name}")

    if args.extract_dir is not None:
        print()
        print(
            "정상 미디어만 임시 추출했습니다:"
        )
        print(args.extract_dir)

    print()
    print(
        "이 검사는 파일 존재/ZIP 무결성만 "
        "확인합니다."
    )
    print(
        "PowerPoint 실제 재생 성공 여부와 "
        "사용 허락 여부는 확인하지 않습니다."
    )


if __name__ == "__main__":
    main()