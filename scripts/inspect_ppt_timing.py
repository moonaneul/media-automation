from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


NS = {
    "p": (
        "http://schemas.openxmlformats.org/"
        "presentationml/2006/main"
    ),
    "a": (
        "http://schemas.openxmlformats.org/"
        "drawingml/2006/main"
    ),
    "r": (
        "http://schemas.openxmlformats.org/"
        "officeDocument/2006/relationships"
    ),
}

REL_NS = {
    "rel": (
        "http://schemas.openxmlformats.org/"
        "package/2006/relationships"
    ),
}


def local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    return tag


def load_relationships(
    archive: zipfile.ZipFile,
    slide_number: int,
) -> dict[str, dict[str, str]]:
    path = (
        "ppt/slides/_rels/"
        f"slide{slide_number}.xml.rels"
    )

    if path not in archive.namelist():
        return {}

    root = ET.fromstring(
        archive.read(path)
    )

    result = {}

    for rel in root:
        rel_id = rel.attrib.get("Id")

        if rel_id is None:
            continue

        result[rel_id] = {
            "type": rel.attrib.get(
                "Type",
                "",
            ),
            "target": rel.attrib.get(
                "Target",
                "",
            ),
        }

    return result


def find_media_relationships(
    relationships: dict[
        str,
        dict[str, str],
    ],
) -> list[
    tuple[str, str, str]
]:
    result = []

    for rel_id, data in relationships.items():
        rel_type = data["type"]
        target = data["target"]

        if (
            "media" in rel_type.lower()
            or "audio" in rel_type.lower()
            or "video" in rel_type.lower()
            or "/media/" in target.lower()
            or target.lower().endswith(
                (
                    ".mp3",
                    ".mp4",
                    ".wav",
                    ".m4a",
                )
            )
        ):
            result.append(
                (
                    rel_id,
                    rel_type,
                    target,
                )
            )

    return result


def print_timing_tree(
    element: ET.Element,
    *,
    depth: int = 0,
) -> None:
    name = local_name(
        element.tag
    )

    interesting = {
        "timing",
        "tnLst",
        "par",
        "seq",
        "cTn",
        "childTnLst",
        "subTnLst",
        "stCondLst",
        "endCondLst",
        "prevCondLst",
        "nextCondLst",
        "cond",
        "tgtEl",
        "spTgt",
        "sndTgt",
        "video",
        "audio",
        "cMediaNode",
        "cmd",
    }

    if name in interesting:
        indent = "  " * depth

        attributes = " ".join(
            f'{key}="{value}"'
            for key, value
            in element.attrib.items()
        )

        if attributes:
            print(
                f"{indent}{name} "
                f"{attributes}"
            )
        else:
            print(
                f"{indent}{name}"
            )

    for child in element:
        print_timing_tree(
            child,
            depth=depth + 1,
        )


def inspect_slide(
    archive: zipfile.ZipFile,
    slide_number: int,
) -> None:
    slide_path = (
        f"ppt/slides/"
        f"slide{slide_number}.xml"
    )

    if slide_path not in archive.namelist():
        return

    relationships = (
        load_relationships(
            archive,
            slide_number,
        )
    )

    media_relationships = (
        find_media_relationships(
            relationships
        )
    )

    xml = archive.read(
        slide_path
    )

    root = ET.fromstring(
        xml
    )

    timing = root.find(
        "p:timing",
        NS,
    )

    has_media_markup = any(
        local_name(element.tag)
        in {
            "video",
            "audio",
            "cMediaNode",
        }
        for element in root.iter()
    )

    if (
        not media_relationships
        and timing is None
        and not has_media_markup
    ):
        return

    print()
    print(
        "=" * 72
    )
    print(
        f"SLIDE {slide_number}"
    )
    print(
        "=" * 72
    )

    if media_relationships:
        print()
        print(
            "[MEDIA RELATIONSHIPS]"
        )

        for (
            rel_id,
            rel_type,
            target,
        ) in media_relationships:
            print(
                f"{rel_id}"
            )
            print(
                f"  type   : {rel_type}"
            )
            print(
                f"  target : {target}"
            )

    else:
        print()
        print(
            "[MEDIA RELATIONSHIPS]"
        )
        print(
            "none"
        )

    print()
    print(
        "[TIMING]"
    )

    if timing is None:
        print(
            "none"
        )
        return

    print_timing_tree(
        timing
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "PowerPoint 슬라이드의 "
            "미디어/재생 timing XML 검사"
        )
    )

    parser.add_argument(
        "pptx",
        type=Path,
    )

    args = parser.parse_args()

    if not args.pptx.exists():
        raise FileNotFoundError(
            args.pptx
        )

    with zipfile.ZipFile(
        args.pptx
    ) as archive:
        slide_paths = [
            name
            for name
            in archive.namelist()
            if (
                name.startswith(
                    "ppt/slides/slide"
                )
                and name.endswith(
                    ".xml"
                )
            )
        ]

        slide_numbers = sorted(
            int(
                Path(path)
                .stem
                .replace(
                    "slide",
                    "",
                )
            )
            for path
            in slide_paths
        )

        print(
            f"PPTX: {args.pptx}"
        )
        print(
            f"slides: {len(slide_numbers)}"
        )

        for slide_number in slide_numbers:
            inspect_slide(
                archive,
                slide_number,
            )


if __name__ == "__main__":
    main()