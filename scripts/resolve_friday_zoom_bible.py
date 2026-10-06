from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml


def normalize_reference(
    value: str,
) -> str:
    return (
        str(value)
        .strip()
        .replace("-", "~")
        .replace("～", "~")
    )


def parse_args():
    p = argparse.ArgumentParser()

    p.add_argument(
        "--requests",
        required=True,
    )

    p.add_argument(
        "--library",
        default="data/bible_library.yaml",
    )

    p.add_argument(
        "--output",
    )

    return p.parse_args()


def main():
    args = parse_args()

    request_path = Path(
        args.requests
    )

    library_path = Path(
        args.library
    )

    requests = yaml.safe_load(
        request_path.read_text(
            encoding="utf-8-sig"
        )
    ) or {}

    library = yaml.safe_load(
        library_path.read_text(
            encoding="utf-8-sig"
        )
    ) or {}

    passages = library.get(
        "passages",
        {}
    )

    normalized_lookup = {
        normalize_reference(reference):
            (reference, passage)
        for reference, passage
        in passages.items()
    }

    requested = requests.get(
        "requests",
        []
    )

    resolved = {}
    missing = []

    for item in requested:
        reference = item.get(
            "reference"
        )

        if not reference:
            continue

        normalized = normalize_reference(
            reference
        )

        found = normalized_lookup.get(
            normalized
        )

        if not found:
            missing.append(
                reference
            )
            continue

        original_reference, passage = found

        clean = copy.deepcopy(
            passage
        )

        clean.pop(
            "_source",
            None,
        )

        # 요청한 표기를 key로 사용.
        resolved[
            reference
        ] = clean

    if missing:
        print()
        print(
            "BIBLE RESOLVE: NOT READY"
        )
        print(
            "=" * 60
        )

        for reference in missing:
            print(
                f"MISSING: {reference}"
            )

        print()
        print(
            "개역개정 원문 데이터가 "
            "로컬 라이브러리에 없습니다."
        )
        print(
            "본문을 임의 생성하거나 "
            "다른 번역본으로 대체하지 않습니다."
        )

        raise SystemExit(2)

    token = (
        request_path.stem
        .replace(
            "friday_zoom_",
            "",
        )
        .replace(
            "_bible_requests",
            "",
        )
    )

    output = (
        Path(args.output)
        if args.output
        else Path(
            "output/friday_zoom_intake"
        )
        / f"friday-zoom-{token}-bible.yaml"
    )

    output.write_text(
        yaml.safe_dump(
            {
                "passages": resolved,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "BIBLE RESOLVE: PASS"
    )
    print(
        "=" * 60
    )

    for reference in resolved:
        print(
            f"OK: {reference}"
        )

    print(
        f"output: {output}"
    )


if __name__ == "__main__":
    main()
