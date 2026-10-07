from __future__ import annotations

import argparse
from pathlib import Path

import yaml


VALID_FIELDS = {
    "opening_song_1",
    "opening_song_2",
    "opening_song_3",
    "separate_hymn",
    "second_service_prayer",
    "church_news",
    "offering_hymn",
    "second_service_offering_prayer",
    "special_song",
    "sermon_title",
    "scripture",
    "additional_scripture",
    "decision_hymn",
}


def load(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def save(path: Path, data):
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", required=True)
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--ignore", action="append", default=[])
    parser.add_argument("--assign", action="append", default=[], metavar="FIELD=TEXT")
    args = parser.parse_args()

    path = Path(args.intake)
    if not path.exists():
        raise SystemExit(f"ERROR: intake not found: {path}")

    data = load(path)
    pending = list(data.get("review_items", []))

    if args.show:
        print("\n=== Sunday Review ===")
        if not pending:
            print("No pending review items.")
        else:
            for index, item in enumerate(pending, start=1):
                print(f"{index}. {item}")
        if not args.ignore and not args.assign:
            return

    changed = False

    for text in args.ignore:
        if text not in pending:
            raise SystemExit(f"ERROR: REVIEW 문장을 찾을 수 없습니다: {text}")
        pending.remove(text)
        print(f"IGNORED: {text}")
        changed = True

    for expression in args.assign:
        if "=" not in expression:
            raise SystemExit("ERROR: --assign must be FIELD=TEXT")
        field, text = expression.split("=", 1)
        field = field.strip()
        text = text.strip()

        if field not in VALID_FIELDS:
            raise SystemExit(f"ERROR: unsupported field: {field}")
        if text not in pending:
            raise SystemExit(f"ERROR: REVIEW 문장을 찾을 수 없습니다: {text}")

        target = data["fields"][field]
        if target.get("status") == "provided" and target.get("value"):
            raise SystemExit(
                f"ERROR: {field} already has value: {target['value']!r}"
            )

        target["status"] = "provided"
        target["value"] = text
        target["review_required"] = False
        pending.remove(text)
        print(f"ASSIGNED: {field} <- {text}")
        changed = True

    data["review_items"] = pending
    data["review_required"] = bool(pending)

    if changed:
        save(path, data)
        print(f"UPDATED: {path}")

    if pending:
        print("REVIEW: STILL REQUIRED")
        for item in pending:
            print(f"  - {item}")
        raise SystemExit(3)

    print("REVIEW: COMPLETE")


if __name__ == "__main__":
    main()
