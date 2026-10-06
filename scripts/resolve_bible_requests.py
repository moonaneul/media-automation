from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml

from media_automation.bible.master import (
    extract_same_chapter_passage,
)


def normalize_reference(value: str) -> str:
    return (
        str(value)
        .strip()
        .replace("-", "~")
        .replace("～", "~")
    )


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}


def resolve_from_range_library(library: dict, reference: str):
    passages = library.get("passages", {})
    if not isinstance(passages, dict):
        return None

    normalized_lookup = {
        normalize_reference(key): (key, passage)
        for key, passage in passages.items()
    }
    found = normalized_lookup.get(normalize_reference(reference))
    if not found:
        return None

    _, passage = found
    clean = copy.deepcopy(passage)
    clean.pop("_source", None)
    return clean


def resolve_from_master(master: dict, reference: str):
    if not master:
        return None
    return extract_same_chapter_passage(master, reference)


def resolve_requests(requests: dict, library: dict, master: dict) -> tuple[dict, list[tuple[str, str]]]:
    resolved = {}
    missing = []

    for item in requests.get("requests", []):
        reference = item.get("reference")
        if not reference:
            continue
        reference = str(reference).strip()

        passage = resolve_from_range_library(library, reference)
        if passage is not None:
            resolved[reference] = passage
            continue

        try:
            passage = resolve_from_master(master, reference)
        except (ValueError, KeyError) as error:
            missing.append((reference, str(error)))
            continue

        if passage is None:
            missing.append((reference, "검증된 Bible master가 없습니다."))
            continue

        resolved[reference] = passage

    return resolved, missing


def main():
    parser = argparse.ArgumentParser(description="공용 개역개정 Bible resolver")
    parser.add_argument("--requests", required=True)
    parser.add_argument("--library", default="data/bible_library.yaml")
    parser.add_argument("--master", default="data/private/bible_master.yaml")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    request_path = Path(args.requests)
    library_path = Path(args.library)
    master_path = Path(args.master)
    output_path = Path(args.output)

    requests = load_yaml(request_path)
    library = load_yaml(library_path)
    master = load_yaml(master_path)

    resolved, missing = resolve_requests(requests, library, master)

    if missing:
        print("\nBIBLE RESOLVE: NOT READY")
        print("=" * 60)
        for reference, reason in missing:
            print(f"MISSING: {reference}")
            print(f"  reason: {reason}")
        print()
        if not master:
            print("검증된 개역개정 전체 Bible master가 아직 등록되지 않았습니다.")
            print("교회가 보유한 검증본 YAML/JSON을 한 번 등록하면 이후 같은 원문을 공용으로 사용합니다.")
        print("본문을 임의 생성하거나 다른 번역본으로 대체하지 않습니다.")
        raise SystemExit(2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(
            {"passages": resolved},
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print("\nBIBLE RESOLVE: PASS")
    print("=" * 60)
    for reference in resolved:
        print(f"OK: {reference}")
    print(f"output: {output_path}")


if __name__ == "__main__":
    main()
