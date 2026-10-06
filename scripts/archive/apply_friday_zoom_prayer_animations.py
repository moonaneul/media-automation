from pathlib import Path
import argparse
import re

import win32com.client


PREFIX = "FridayZoomPrayerTopic"


def topic_number(shape):
    match = re.search(
        r"(\d+)$",
        shape.Name,
    )

    if not match:
        return 999

    return int(
        match.group(1)
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--pptx",
        required=True,
    )

    args = parser.parse_args()

    path = Path(
        args.pptx
    ).resolve()

    if not path.exists():
        raise SystemExit(
            f"PPTX not found: {path}"
        )

    app = win32com.client.DispatchEx(
        "PowerPoint.Application"
    )

    presentation = app.Presentations.Open(
        str(path),
        False,
        False,
        False,
    )

    changed = 0

    try:
        for slide_no in range(
            1,
            presentation.Slides.Count + 1,
        ):
            slide = presentation.Slides(
                slide_no
            )

            topics = []

            for i in range(
                1,
                slide.Shapes.Count + 1,
            ):
                shape = slide.Shapes(i)

                try:
                    name = shape.Name
                except Exception:
                    continue

                if name.startswith(
                    PREFIX
                ):
                    topics.append(
                        shape
                    )

            if len(topics) < 2:
                continue

            topics.sort(
                key=topic_number
            )

            sequence = (
                slide.TimeLine
                .MainSequence
            )

            # ??? ? ?? ??????
            # ?? ???? ???.
            already_animated = False

            for i in range(
                1,
                sequence.Count + 1,
            ):
                effect = sequence.Item(i)

                try:
                    name = effect.Shape.Name
                except Exception:
                    continue

                if name.startswith(
                    PREFIX
                ):
                    already_animated = True
                    break

            if already_animated:
                print(
                    f"slide {slide_no}: "
                    "animation already exists"
                )
                continue

            count = len(topics)

            # --------------------------------
            # ? ????
            # ??:
            # entrance + WithPrevious
            # --------------------------------

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

            # --------------------------------
            # ?? ??
            #
            # ?? ??:
            # ?? -> exit
            #
            # ?? ??:
            # exit? ??/?? entrance
            # --------------------------------

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
                exit_effect.Timing.Duration = 0.5

                # ?? 09-18 ?????:
                # ? ?? ??? exit? ??? ??.
                #
                # ??? ?? ?? 2??? ??:
                # ?? exit ?? ??.
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

            print(
                f"slide {slide_no}: "
                f"{count} prayer topics animated"
            )

        presentation.Save()

    finally:
        presentation.Close()
        app.Quit()

    print()
    print(
        f"OK: animated {changed} prayer slides"
    )


if __name__ == "__main__":
    main()
