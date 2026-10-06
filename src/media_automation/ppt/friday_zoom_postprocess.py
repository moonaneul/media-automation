from __future__ import annotations

from pathlib import Path
from typing import Any

import win32com.client


TEMPLATE_PREFIX = "FridayZoomTemplate_"
PRAYER_PREFIX = "FridayZoomPrayerTopic"

CHURCH_NAME = (
    "\ud558\ub298\ube5b\uae30\uc068"
)

SERVICE_NAME = (
    "\uae08\uc694\uae30\ub3c4\ud68c"
)

PRE_SERVICE_MESSAGE = (
    "\uc9c0\uae08\uc740 "
    "\uae30\ub3c4\ub85c "
    "\uc608\ubc30\ub97c "
    "\uc900\ube44\ud558\ub294 "
    "\uc2dc\uac04\uc785\ub2c8\ub2e4"
)

PERSONAL_PRAYER_DEFAULT = (
    "\uc9c0\uae08\uc740 "
    "\uac1c\uc778 "
    "\uae30\ub3c4 "
    "\uc2dc\uac04\uc785\ub2c8\ub2e4."
)


def _safe(getter, default=None):
    try:
        return getter()
    except Exception:
        return default


def _date_text(value: Any) -> str:
    if hasattr(value, "strftime"):
        return value.strftime(
            "%Y.%m.%d"
        )

    text = str(value)

    return text.replace(
        "-",
        ".",
    )


def _delete_template_shapes(slide) -> None:
    for index in range(
        slide.Shapes.Count,
        0,
        -1,
    ):
        shape = slide.Shapes(index)

        name = _safe(
            lambda: shape.Name,
            "",
        )

        if str(name).startswith(
            TEMPLATE_PREFIX
        ):
            shape.Delete()


def _delete_text_shapes(slide) -> None:
    for index in range(
        slide.Shapes.Count,
        0,
        -1,
    ):
        shape = slide.Shapes(index)

        name = _safe(
            lambda: shape.Name,
            "",
        )

        if str(name).startswith(
            TEMPLATE_PREFIX
        ):
            continue

        has_text = _safe(
            lambda: (
                shape.HasTextFrame
                and shape.TextFrame.HasText
            ),
            False,
        )

        if has_text:
            shape.Delete()


def _add_text(
    slide,
    *,
    name: str,
    text: str,
    left: float,
    top: float,
    width: float,
    height: float,
    font_size: float,
    align: int = 1,
    vertical_anchor: int = 3,
):
    shape = slide.Shapes.AddTextbox(
        1,
        left,
        top,
        width,
        height,
    )

    shape.Name = (
        TEMPLATE_PREFIX + name
    )

    frame = shape.TextFrame

    frame.WordWrap = -1

    _safe(
        lambda: setattr(
            frame,
            "VerticalAnchor",
            vertical_anchor,
        )
    )

    text_range = frame.TextRange

    text_range.Text = text

    text_range.ParagraphFormat.Alignment = (
        align
    )

    text_range.Font.Size = font_size

    text_range.Font.Color.RGB = (
        255
        + (255 << 8)
        + (255 << 16)
    )

    return shape


def _add_page_number(
    slide,
    number: int,
) -> None:
    _add_text(
        slide,
        name="PageNumber",
        text=str(number),
        left=900.0,
        top=503.0,
        width=45.0,
        height=22.0,
        font_size=11,
        align=2,
    )


def _add_header(
    slide,
    date_text: str,
) -> None:
    left_shape = _add_text(
        slide,
        name="HeaderLeft",
        text=(
            CHURCH_NAME
            + " "
            + SERVICE_NAME
        ),
        left=8.0,
        top=10.0,
        width=220.0,
        height=22.0,
        font_size=10,
        align=1,
    )

    left_shape.TextFrame.TextRange.Font.Bold = 0

    right_shape = _add_text(
        slide,
        name="HeaderRight",
        text=date_text,
        left=815.0,
        top=10.0,
        width=120.0,
        height=22.0,
        font_size=10,
        align=3,
    )

    right_shape.TextFrame.TextRange.Font.Bold = 0


def _range_value(
    slide_ranges,
    key: str,
):
    value = slide_ranges.get(
        key
    )

    if value is None:
        return None

    return (
        int(value.start),
        int(value.end),
    )


def _weekly_title(
    weekly,
    key: str,
):
    if key.startswith(
        "opening_songs["
    ):
        index = int(
            key.split(
                "[",
                1,
            )[1].split(
                "]",
                1,
            )[0]
        )

        songs = getattr(
            weekly,
            "opening_songs",
            (),
        )

        if index >= len(songs):
            return None

        return getattr(
            songs[index],
            "title",
            None,
        )

    item = getattr(
        weekly,
        key,
        None,
    )

    if item is None:
        return None

    return getattr(
        item,
        "title",
        None,
    )


def _decorate_pre_service(
    presentation,
    slide_ranges,
    date_text: str,
) -> None:
    slide_range = _range_value(
        slide_ranges,
        "pre_service",
    )

    if slide_range is None:
        return

    slide = presentation.Slides(
        slide_range[0]
    )

    _delete_text_shapes(
        slide
    )

    # ?? ??? 16:9 ???
    # ?? ??? ??? ????.
    _add_text(
        slide,
        name="PreServiceDate",
        text=date_text,
        left=180.0,
        top=170.0,
        width=600.0,
        height=38.0,
        font_size=24,
        align=2,
    )

    _add_text(
        slide,
        name="PreServiceTitle",
        text=SERVICE_NAME,
        left=150.0,
        top=235.0,
        width=660.0,
        height=65.0,
        font_size=44,
        align=2,
    )

    _add_text(
        slide,
        name="PreServiceMessage",
        text=PRE_SERVICE_MESSAGE,
        left=100.0,
        top=310.0,
        width=760.0,
        height=55.0,
        font_size=26,
        align=2,
    )




def _decorate_song_titles(
    presentation,
    weekly,
    slide_ranges,
) -> None:
    keys = [
        "opening_songs[0]",
        "opening_songs[1]",
        "song_after_prayer",
        "response_song",
        "intercession_song",
    ]

    for key in keys:
        slide_range = _range_value(
            slide_ranges,
            key,
        )

        if slide_range is None:
            continue

        title = _weekly_title(
            weekly,
            key,
        )

        if not title:
            continue

        slide = presentation.Slides(
            slide_range[0]
        )

        _add_text(
            slide,
            name=(
                "SongTitle_"
                + key
                .replace("[", "_")
                .replace("]", "")
            ),
            text=str(title),
            left=80.0,
            top=8.0,
            width=800.0,
            height=50.0,
            font_size=32,
            align=1,
        )


def _decorate_headers(
    presentation,
    slide_ranges,
    date_text: str,
) -> None:
    prayer_keys = [
        "first_prayer",
        "word_prayer",
        "community_prayer",
    ]

    for key in prayer_keys:
        slide_range = _range_value(
            slide_ranges,
            key,
        )

        if slide_range is None:
            continue

        for slide_no in range(
            slide_range[0],
            slide_range[1] + 1,
        ):
            _add_header(
                presentation.Slides(
                    slide_no
                ),
                date_text,
            )

    scripture_range = _range_value(
        slide_ranges,
        "scripture",
    )

    if scripture_range is not None:
        # The first slide is the large
        # scripture-reference screen.
        for slide_no in range(
            scripture_range[0] + 1,
            scripture_range[1] + 1,
        ):
            _add_header(
                presentation.Slides(
                    slide_no
                ),
                date_text,
            )

    additional_range = _range_value(
        slide_ranges,
        "additional_scripture",
    )

    if additional_range is not None:
        for slide_no in range(
            additional_range[0],
            additional_range[1] + 1,
        ):
            _add_header(
                presentation.Slides(
                    slide_no
                ),
                date_text,
            )


def _decorate_personal_prayer(
    presentation,
    weekly,
    slide_ranges,
) -> None:
    slide_range = _range_value(
        slide_ranges,
        "personal_prayer",
    )

    if slide_range is None:
        return

    slide = presentation.Slides(
        slide_range[0]
    )

    _delete_text_shapes(
        slide
    )

    item = getattr(
        weekly,
        "personal_prayer",
        None,
    )

    raw = getattr(
        item,
        "text",
        None,
    )

    lines = [
        line.strip()
        for line in str(
            raw or ""
        ).splitlines()
        if line.strip()
    ]

    headline = None
    supporting = []

    for line in lines:
        if (
            headline is None
            and "\uac1c\uc778 \uae30\ub3c4 \uc2dc\uac04"
            in line
        ):
            headline = line
        else:
            supporting.append(
                line
            )

    if headline is None:
        headline = (
            PERSONAL_PRAYER_DEFAULT
        )

    detail = "\r".join(
        supporting
    )

    _add_text(
        slide,
        name="PersonalPrayerHeadline",
        text=headline,
        left=129.5,
        top=235.0,
        width=701.0,
        height=85.0,
        font_size=48,
        align=2,
    )

    if detail:
        detail_shape = _add_text(
            slide,
            name="PersonalPrayerDetail",
            text=detail,
            left=129.5,
            top=355.0,
            width=701.0,
            height=110.0,
            font_size=30,
            align=2,
        )

        detail_range = (
            detail_shape.TextFrame.TextRange
        )

        detail_range.ParagraphFormat.LineRuleWithin = -1
        detail_range.ParagraphFormat.SpaceWithin = 1.45


def _apply_prayer_animations(
    presentation,
) -> int:
    changed = 0

    for slide_no in range(
        1,
        presentation.Slides.Count + 1,
    ):
        slide = presentation.Slides(
            slide_no
        )

        topics = []

        for index in range(
            1,
            slide.Shapes.Count + 1,
        ):
            shape = slide.Shapes(index)

            name = _safe(
                lambda: shape.Name,
                "",
            )

            if str(name).startswith(
                PRAYER_PREFIX
            ):
                topics.append(
                    shape
                )

        if len(topics) < 2:
            continue

        def topic_number(shape):
            name = str(
                shape.Name
            )

            suffix = name[
                len(PRAYER_PREFIX):
            ]

            try:
                return int(suffix)
            except ValueError:
                return 999

        topics.sort(
            key=topic_number
        )

        sequence = (
            slide.TimeLine.MainSequence
        )

        already_exists = False

        for index in range(
            1,
            sequence.Count + 1,
        ):
            effect = sequence.Item(
                index
            )

            effect_shape = _safe(
                lambda: effect.Shape,
            )

            effect_name = _safe(
                lambda: effect_shape.Name,
                "",
            )

            if str(
                effect_name
            ).startswith(
                PRAYER_PREFIX
            ):
                already_exists = True
                break

        if already_exists:
            continue

        count = len(
            topics
        )

        first = sequence.AddEffect(
            topics[0],
            10,
            0,
            2,
        )

        first.Timing.Duration = (
            1.5
            if count >= 3
            else 0.5
        )

        for index in range(
            1,
            count,
        ):
            previous = topics[
                index - 1
            ]

            current = topics[
                index
            ]

            exit_effect = (
                sequence.AddEffect(
                    previous,
                    10,
                    0,
                    1,
                )
            )

            exit_effect.Exit = -1

            exit_effect.Timing.Duration = (
                0.5
            )

            if (
                count >= 3
                and index == 1
            ):
                trigger = 2
                duration = 1.5
            else:
                trigger = 3
                duration = 0.5

            entrance = (
                sequence.AddEffect(
                    current,
                    10,
                    0,
                    trigger,
                )
            )

            entrance.Timing.Duration = (
                duration
            )

        changed += 1

    return changed


def _bold_all_text(presentation) -> None:
    for slide_index in range(
        1,
        presentation.Slides.Count + 1,
    ):
        slide = presentation.Slides(
            slide_index
        )

        for shape_index in range(
            1,
            slide.Shapes.Count + 1,
        ):
            shape = slide.Shapes(
                shape_index
            )

            try:
                name = str(
                    shape.Name
                )
            except Exception:
                name = ""

            try:
                has_text = (
                    shape.HasTextFrame
                    and shape.TextFrame.HasText
                )
            except Exception:
                has_text = False

            if not has_text:
                continue

            # Header must remain regular weight.
            if name.startswith(
                "FridayZoomTemplate_Header"
            ):
                shape.TextFrame.TextRange.Font.Bold = 0
                continue

            shape.TextFrame.TextRange.Font.Bold = -1



def finalize_friday_zoom_powerpoint(
    pptx_path: str | Path,
    *,
    weekly,
    slide_ranges,
) -> int:
    pptx_path = Path(
        pptx_path
    ).resolve()

    date_text = _date_text(
        weekly.date
    )

    app = win32com.client.DispatchEx(
        "PowerPoint.Application"
    )

    presentation = app.Presentations.Open(
        str(pptx_path),
        False,
        False,
        False,
    )

    try:
        for slide_no in range(
            1,
            presentation.Slides.Count + 1,
        ):
            _delete_template_shapes(
                presentation.Slides(
                    slide_no
                )
            )

        _decorate_pre_service(
            presentation,
            slide_ranges,
            date_text,
        )

        _decorate_song_titles(
            presentation,
            weekly,
            slide_ranges,
        )

        _decorate_headers(
            presentation,
            slide_ranges,
            date_text,
        )

        _decorate_personal_prayer(
            presentation,
            weekly,
            slide_ranges,
        )

        # Page numbers are added last so they
        # survive text cleanup on special slides.
        for slide_no in range(
            1,
            presentation.Slides.Count + 1,
        ):
            _add_page_number(
                presentation.Slides(
                    slide_no
                ),
                slide_no,
            )

        _bold_all_text(
            presentation
        )

        animation_count = (
            _apply_prayer_animations(
                presentation
            )
        )

        presentation.Save()

    finally:
        presentation.Close()
        app.Quit()

    return animation_count
