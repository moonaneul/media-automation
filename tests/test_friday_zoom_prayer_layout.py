from media_automation.ppt.base import (
    create_16x9_presentation,
)
from media_automation.ppt.friday_zoom import (
    add_prayer_topics_slide,
)


def test_prayer_topics_use_separate_shapes():
    prs = create_16x9_presentation()

    slide = add_prayer_topics_slide(
        prs,
        [
            "first topic",
            "second topic",
            "third topic",
        ],
    )

    shapes = [
        shape
        for shape in slide.shapes
        if shape.name.startswith(
            "FridayZoomPrayerTopic"
        )
    ]

    assert len(shapes) == 3

    assert [
        shape.name
        for shape in shapes
    ] == [
        "FridayZoomPrayerTopic1",
        "FridayZoomPrayerTopic2",
        "FridayZoomPrayerTopic3",
    ]

    # ?? Zoom?? ?? ??? ?? ???
    # animation?? ?? ??? ? ??.
    assert len(
        {
            (
                shape.left,
                shape.top,
                shape.width,
                shape.height,
            )
            for shape in shapes
        }
    ) == 1
