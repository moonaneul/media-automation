from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path

import win32com.client
import yaml


HEADER_LEFT = "FridayZoomTemplate_HeaderLeft"
HEADER_RIGHT = "FridayZoomTemplate_HeaderRight"
PRAYER_PREFIX = "FridayZoomPrayerTopic"

OLD_BAPTISM = "\uC138\uB840"   # 세례


def args():
    p = argparse.ArgumentParser()
    p.add_argument("--pptx", required=True)
    p.add_argument("--weekly", required=True)
    p.add_argument("--bible", required=True)
    p.add_argument("--media")
    return p.parse_args()


def safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def normalize_ref(value: str) -> str:
    return str(value).replace("-", "~")


def main():
    a = args()

    pptx = Path(a.pptx).resolve()
    weekly = yaml.safe_load(
        Path(a.weekly).read_text(encoding="utf-8")
    )
    bible = yaml.safe_load(
        Path(a.bible).read_text(encoding="utf-8")
    )

    failures = []
    warnings = []

    app = win32com.client.DispatchEx(
        "PowerPoint.Application"
    )

    pres = app.Presentations.Open(
        str(pptx),
        False,
        False,
        False,
    )

    slide_texts = {}
    slide_shapes = {}
    prayer_effects = {}

    try:
        slide_count = pres.Slides.Count

        ratio = (
            float(pres.PageSetup.SlideWidth)
            / float(pres.PageSetup.SlideHeight)
        )

        if abs(ratio - 16 / 9) < 0.001:
            print(
                f"PASS : aspect ratio 16:9 ({ratio:.4f})"
            )
        else:
            failures.append(
                f"aspect ratio != 16:9 ({ratio:.4f})"
            )

        print(
            f"INFO : slide count = {slide_count}"
        )

        for n in range(1, slide_count + 1):
            slide = pres.Slides(n)

            texts = []
            shapes = {}

            for i in range(
                1,
                slide.Shapes.Count + 1,
            ):
                shape = slide.Shapes(i)

                name = str(
                    safe(
                        lambda: shape.Name,
                        "",
                    )
                )

                text = ""

                if safe(
                    lambda: (
                        shape.HasTextFrame
                        and shape.TextFrame.HasText
                    ),
                    False,
                ):
                    text = str(
                        safe(
                            lambda: (
                                shape.TextFrame
                                .TextRange.Text
                            ),
                            "",
                        )
                    ).strip()

                if text:
                    texts.append(text)

                shapes[name] = {
                    "text": text,
                    "bold": safe(
                        lambda: (
                            shape.TextFrame
                            .TextRange.Font.Bold
                        ),
                        None,
                    ),
                    "left": safe(
                        lambda: float(shape.Left),
                        None,
                    ),
                }

            slide_texts[n] = "\n".join(texts)
            slide_shapes[n] = shapes

            seq = slide.TimeLine.MainSequence

            effects = []

            for i in range(1, seq.Count + 1):
                effect = seq.Item(i)

                shape_name = safe(
                    lambda: effect.Shape.Name,
                    "",
                )

                if str(shape_name).startswith(
                    PRAYER_PREFIX
                ):
                    effects.append(
                        str(shape_name)
                    )

            prayer_effects[n] = effects

    finally:
        pres.Close()
        app.Quit()

    all_text = "\n".join(
        slide_texts.values()
    )

    # --------------------------------------------------------
    # Dynamic date
    # --------------------------------------------------------

    date_value = str(
        weekly.get("date", "")
    )

    expected_date = date_value.replace(
        "-",
        ".",
    )

    if expected_date and expected_date in all_text:
        print(
            f"PASS : weekly date = {expected_date}"
        )
    else:
        failures.append(
            f"weekly date not found: {expected_date}"
        )

    # --------------------------------------------------------
    # Header structure + weight
    # --------------------------------------------------------

    header_count = 0
    bold_headers = []

    for n, shapes in slide_shapes.items():
        left = shapes.get(
            HEADER_LEFT
        )
        right = shapes.get(
            HEADER_RIGHT
        )

        if left and right:
            header_count += 1

            if left["bold"] not in (
                0,
                False,
            ):
                bold_headers.append(n)

            if right["bold"] not in (
                0,
                False,
            ):
                bold_headers.append(n)

    if header_count:
        print(
            f"PASS : split headers found on "
            f"{header_count} slides"
        )
    else:
        failures.append(
            "split Friday Zoom headers not found"
        )

    if bold_headers:
        failures.append(
            "header unexpectedly bold on slides: "
            + ", ".join(
                map(
                    str,
                    sorted(
                        set(bold_headers)
                    ),
                )
            )
        )
    else:
        print(
            "PASS : header text is regular weight"
        )

    # --------------------------------------------------------
    # Bible passages
    # --------------------------------------------------------

    passages = bible.get(
        "passages",
        {}
    )

    missing_verses = []
    duplicate_verses = []

    for reference, passage in passages.items():
        verses = passage.get(
            "verses",
            {}
        )

        for number, text in verses.items():
            displayed = str(text).replace(
                OLD_BAPTISM,
                "\uCE68\uB840",
            )

            count = all_text.count(
                displayed
            )

            if count == 0:
                missing_verses.append(
                    f"{reference}:{number}"
                )

            elif count > 1:
                duplicate_verses.append(
                    f"{reference}:{number} x{count}"
                )

    if not missing_verses:
        print(
            "PASS : all Bible verses present"
        )
    else:
        failures.append(
            "missing verses: "
            + ", ".join(missing_verses)
        )

    if not duplicate_verses:
        print(
            "PASS : no duplicated Bible verse bodies"
        )
    else:
        failures.append(
            "duplicated verses: "
            + ", ".join(duplicate_verses)
        )

    if OLD_BAPTISM in all_text:
        failures.append(
            "unconverted baptism wording remains"
        )
    else:
        print(
            "PASS : baptism wording conversion check"
        )

    # --------------------------------------------------------
    # Sermon title/reference
    # --------------------------------------------------------

    sermon = weekly.get(
        "sermon_title",
        {}
    )

    title = sermon.get(
        "text",
        ""
    )

    if title:
        if title in all_text:
            print(
                "PASS : sermon title present"
            )
        else:
            failures.append(
                f"sermon title missing: {title}"
            )

    scripture = weekly.get(
        "scripture",
        {}
    )

    reference = scripture.get(
        "reference",
        ""
    )

    if reference:
        normalized = normalize_ref(
            reference
        )

        if normalized in all_text:
            print(
                f"PASS : sermon/scripture ref "
                f"{normalized}"
            )
        else:
            failures.append(
                f"scripture reference missing: "
                f"{normalized}"
            )

    # --------------------------------------------------------
    # Prayer animation consistency
    # --------------------------------------------------------

    animated_slides = 0

    for n, shapes in slide_shapes.items():
        topic_shapes = [
            name
            for name in shapes
            if name.startswith(
                PRAYER_PREFIX
            )
        ]

        topic_count = len(
            topic_shapes
        )

        if not topic_count:
            continue

        animated_slides += 1

        expected = (
            topic_count * 2 - 1
        )

        actual = len(
            prayer_effects[n]
        )

        if actual == expected:
            print(
                f"PASS : slide {n} prayer "
                f"animation {actual}/{expected}"
            )
        else:
            failures.append(
                f"slide {n} prayer animation "
                f"{actual}/{expected}"
            )

    print(
        f"INFO : animated prayer slides "
        f"= {animated_slides}"
    )

    # --------------------------------------------------------
    # Embedded media
    # --------------------------------------------------------

    media_relationships = 0

    with zipfile.ZipFile(
        pptx,
        "r",
    ) as archive:
        for name in archive.namelist():
            if not re.fullmatch(
                r"ppt/slides/_rels/"
                r"slide\d+\.xml\.rels",
                name,
            ):
                continue

            raw = archive.read(
                name
            ).decode(
                "utf-8",
                errors="ignore",
            )

            media_relationships += len(
                re.findall(
                    r'Target="[^"]*media/',
                    raw,
                )
            )

    print(
        f"INFO : embedded media relationships "
        f"= {media_relationships}"
    )

    if a.media:
        manifest = yaml.safe_load(
            Path(a.media).read_text(
                encoding="utf-8"
            )
        )

        expected_media = len(
            manifest.get(
                "media",
                {}
            )
        )

        if (
            media_relationships
            >= expected_media
        ):
            print(
                f"PASS : media manifest entries "
                f"= {expected_media}"
            )
        else:
            failures.append(
                f"media relationships "
                f"{media_relationships} "
                f"< manifest {expected_media}"
            )

    # --------------------------------------------------------
    # URLs
    # --------------------------------------------------------

    if re.search(
        r"https?://|www\.",
        all_text,
        re.IGNORECASE,
    ):
        warnings.append(
            "visible URL text found"
        )
    else:
        print(
            "PASS : no visible URL text"
        )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print()
    print("=" * 68)

    for value in warnings:
        print(
            "WARN :",
            value,
        )

    if failures:
        print(
            f"FINAL: FAIL "
            f"({len(failures)} issue(s))"
        )

        for value in failures:
            print(
                "FAIL :",
                value,
            )

        raise SystemExit(1)

    print("FINAL: PASS")


if __name__ == "__main__":
    main()
