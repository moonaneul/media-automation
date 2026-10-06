from media_automation.ppt.base import (
    create_16x9_presentation,
)
from media_automation.ppt.friday_zoom import (
    add_personal_prayer_slide,
    add_zoom_sermon_title_slide,
)


def _slide_text(slide):
    values = []

    for shape in slide.shapes:
        if not hasattr(shape, "text"):
            continue

        value = (
            shape.text
            .replace("\v", "\n")
            .strip()
        )

        if value:
            values.append(value)

    return "\n".join(values)


def test_personal_prayer_uses_supplied_text():
    prs = create_16x9_presentation()

    expected = (
        "first personal prayer line\n"
        "second personal prayer line"
    )

    slide = add_personal_prayer_slide(
        prs,
        expected,
    )

    actual = _slide_text(slide)

    assert (
        "first personal prayer line"
        in actual
    )

    assert (
        "second personal prayer line"
        in actual
    )


def test_personal_prayer_allows_missing_text():
    prs = create_16x9_presentation()

    slide = add_personal_prayer_slide(
        prs,
        None,
    )

    actual = _slide_text(slide)

    expected = (
        "\uac1c\uc778 "
        "\uae30\ub3c4 "
        "\uc2dc\uac04"
    )

    assert expected in actual


def test_zoom_sermon_title_normalizes_reference():
    prs = create_16x9_presentation()

    slide = add_zoom_sermon_title_slide(
        prs,
        "test title",
        "\uc655\uc0c1 9:1-10",
    )

    actual = _slide_text(slide)

    assert "\uc655\uc0c1 9:1~10" in actual
    assert "\uc655\uc0c1 9:1-10" not in actual
