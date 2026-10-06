from __future__ import annotations

import argparse
from pathlib import Path

import yaml


MULTILINE_FIELDS = {
    "first_prayer",
    "word_prayer",
    "community_prayer",
    "personal_prayer",
}

SCALAR_FIELDS = {
    "opening_song_1",
    "opening_song_2",
    "song_after_prayer",
    "scripture",
    "sermon_title",
    "additional_scripture",
    "response_song",
    "intercession_song",
}

VALID_FIELDS = (
    MULTILINE_FIELDS
    | SCALAR_FIELDS
)


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--intake",
        required=True,
    )

    parser.add_argument(
        "--show",
        action="store_true",
    )

    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        help="정확히 일치하는 REVIEW 문장을 무시 처리",
    )

    parser.add_argument(
        "--assign",
        action="append",
        default=[],
        metavar="FIELD=TEXT",
        help="REVIEW 문장을 특정 필드로 이동",
    )

    return parser.parse_args()


def load(path):
    return yaml.safe_load(
        path.read_text(
            encoding="utf-8-sig"
        )
    )


def save(path, data):
    path.write_text(
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def show(data):
    items = data.get(
        "review_items",
        [],
    )

    print()
    print(
        "=== Friday Zoom Review ==="
    )

    if not items:
        print(
            "No pending review items."
        )
        return

    for index, item in enumerate(
        items,
        start=1,
    ):
        print(
            f"{index}. {item}"
        )


def remove_review_item(
    pending,
    text,
):
    if text not in pending:
        raise SystemExit(
            "ERROR: REVIEW 문장을 찾을 수 없습니다: "
            + text
        )

    pending.remove(text)


def assign_value(
    data,
    field,
    text,
):
    if field not in VALID_FIELDS:
        raise SystemExit(
            f"ERROR: unsupported field: {field}"
        )

    target = data[
        "fields"
    ][field]

    if field in MULTILINE_FIELDS:
        current = target.get(
            "value"
        )

        if not isinstance(
            current,
            list,
        ):
            current = (
                [current]
                if current
                else []
            )

        current.append(
            text
        )

        target[
            "status"
        ] = "provided"

        target[
            "value"
        ] = current

        target[
            "review_required"
        ] = False

        return

    current_status = target.get(
        "status"
    )

    current_value = target.get(
        "value"
    )

    # 이미 값이 있는데 REVIEW 문장으로
    # 조용히 덮어쓰는 것은 금지한다.
    if (
        current_status == "provided"
        and current_value
    ):
        raise SystemExit(
            f"ERROR: {field} already has value: "
            f"{current_value!r}"
        )

    target[
        "status"
    ] = "provided"

    target[
        "value"
    ] = text

    target[
        "review_required"
    ] = False


def main():
    args = parse_args()

    path = Path(
        args.intake
    )

    if not path.exists():
        raise SystemExit(
            f"ERROR: intake not found: {path}"
        )

    data = load(
        path
    )

    pending = list(
        data.get(
            "review_items",
            [],
        )
    )

    if args.show:
        show(
            data
        )

        if (
            not args.ignore
            and not args.assign
        ):
            return

    changed = False

    # ----------------------------------------
    # Ignore explicitly selected lines
    # ----------------------------------------

    for text in args.ignore:
        remove_review_item(
            pending,
            text,
        )

        print(
            f"IGNORED: {text}"
        )

        changed = True

    # ----------------------------------------
    # Assign REVIEW line to a field
    # Format:
    # field=exact review text
    # ----------------------------------------

    for expression in args.assign:
        if "=" not in expression:
            raise SystemExit(
                "ERROR: --assign must be FIELD=TEXT"
            )

        field, text = (
            expression.split(
                "=",
                1,
            )
        )

        field = field.strip()
        text = text.strip()

        remove_review_item(
            pending,
            text,
        )

        assign_value(
            data,
            field,
            text,
        )

        print(
            f"ASSIGNED: {field} <- {text}"
        )

        changed = True

    data[
        "review_items"
    ] = pending

    data[
        "review_required"
    ] = bool(
        pending
    )

    if changed:
        save(
            path,
            data,
        )

        print()
        print(
            f"UPDATED: {path}"
        )

    print()

    if pending:
        print(
            "REVIEW: STILL REQUIRED"
        )

        for item in pending:
            print(
                f"  - {item}"
            )

        raise SystemExit(3)

    print(
        "REVIEW: COMPLETE"
    )


if __name__ == "__main__":
    main()
