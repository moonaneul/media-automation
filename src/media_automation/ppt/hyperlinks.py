from __future__ import annotations

from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree


R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
SLIDE_XML = re.compile(r"ppt/slides/slide\d+\.xml$")


def _remove_slide_hyperlinks(xml_bytes: bytes) -> tuple[bytes, set[str], int]:
    root = etree.fromstring(xml_bytes)
    removed_relationship_ids: set[str] = set()
    removed = 0

    nodes = root.xpath(
        ".//*[local-name()='hlinkClick' or local-name()='hlinkMouseOver']"
    )
    for node in nodes:
        relationship_id = node.get(f"{{{R_NS}}}id")
        if relationship_id:
            removed_relationship_ids.add(relationship_id)

        parent = node.getparent()
        if parent is not None:
            parent.remove(node)
            removed += 1

    if not removed:
        return xml_bytes, set(), 0

    return (
        etree.tostring(
            root,
            xml_declaration=True,
            encoding="UTF-8",
            standalone=True,
        ),
        removed_relationship_ids,
        removed,
    )


def _remove_relationships(xml_bytes: bytes, relationship_ids: set[str]) -> bytes:
    if not relationship_ids:
        return xml_bytes

    root = etree.fromstring(xml_bytes)
    changed = False

    for relationship in list(root):
        if relationship.tag != f"{{{REL_NS}}}Relationship":
            continue
        if relationship.get("Id") in relationship_ids:
            root.remove(relationship)
            changed = True

    if not changed:
        return xml_bytes

    return etree.tostring(
        root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )


def remove_presentation_hyperlinks(presentation_path: str | Path) -> int:
    """Remove click/text hyperlinks from slide XML in an assembled worship PPT.

    Wednesday in-person worship slides do not require clickable navigation. Imported
    score PPTs can contain internal slide jumps (e.g. slide12.xml) or stale external
    links. Removing both prevents accidental jumps and lets the final QA verify that
    no clickable link remains. Visible URL text is intentionally untouched so QA can
    still flag it.
    """

    path = Path(presentation_path)
    if not path.exists():
        raise FileNotFoundError(path)

    temp = path.with_name(path.name + ".hyperlink-clean.tmp")
    if temp.exists():
        temp.unlink()

    removed_total = 0
    slide_relationship_ids: dict[str, set[str]] = {}

    try:
        with ZipFile(path, "r") as source, ZipFile(
            temp,
            "w",
            compression=ZIP_DEFLATED,
        ) as destination:
            contents: dict[str, bytes] = {}

            for info in source.infolist():
                data = source.read(info.filename)
                if SLIDE_XML.fullmatch(info.filename):
                    data, relationship_ids, removed = _remove_slide_hyperlinks(data)
                    removed_total += removed
                    if relationship_ids:
                        rels_name = (
                            "ppt/slides/_rels/"
                            + Path(info.filename).name
                            + ".rels"
                        )
                        slide_relationship_ids[rels_name] = relationship_ids
                contents[info.filename] = data

            for rels_name, relationship_ids in slide_relationship_ids.items():
                if rels_name in contents:
                    contents[rels_name] = _remove_relationships(
                        contents[rels_name],
                        relationship_ids,
                    )

            for info in source.infolist():
                destination.writestr(info, contents[info.filename])

        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()

    return removed_total
