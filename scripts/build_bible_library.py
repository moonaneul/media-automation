from __future__ import annotations

from pathlib import Path

import yaml


SAMPLE_SOURCE_DIR = Path("samples/weekly")
PRIVATE_SOURCE_DIR = Path("data/private/bible_sources")
OUTPUT = Path("data/bible_library.yaml")


def normalize_reference(value: str) -> str:
    return (
        str(value)
        .strip()
        .replace("-", "~")
        .replace("～", "~")
    )


def source_files() -> list[Path]:
    files = sorted(
        SAMPLE_SOURCE_DIR.glob("*-bible.yaml")
    )

    if PRIVATE_SOURCE_DIR.exists():
        files.extend(
            sorted(
                PRIVATE_SOURCE_DIR.glob("*.yaml")
            )
        )

    return files


def load_source(path: Path) -> dict:
    raw = yaml.safe_load(
        path.read_text(
            encoding="utf-8-sig"
        )
    ) or {}

    if path.is_relative_to(PRIVATE_SOURCE_DIR):
        if raw.get("translation") != "개역개정":
            raise ValueError(
                f"검증 본문의 translation이 개역개정이 아닙니다: {path}"
            )
        if raw.get("validated") is not True:
            raise ValueError(
                f"검증 완료 표시가 없는 본문입니다: {path}"
            )

    return raw


def build_library(files: list[Path]) -> dict:
    library = {
        "translation": "개역개정",
        "passages": {},
    }

    normalized_sources: dict[str, tuple[str, dict]] = {}
    conflicts = []

    for path in files:
        raw = load_source(path)
        passages = raw.get("passages", {})

        if not isinstance(passages, dict):
            raise ValueError(
                f"passages 객체가 필요합니다: {path}"
            )

        for reference, passage in passages.items():
            normalized = normalize_reference(reference)
            existing = normalized_sources.get(normalized)

            if existing is not None:
                existing_reference, existing_value = existing
                comparable_existing = {
                    key: value
                    for key, value in existing_value.items()
                    if key != "_source"
                }

                if comparable_existing != passage:
                    conflicts.append(
                        {
                            "reference": reference,
                            "existing_reference": existing_reference,
                            "existing_source": existing_value.get("_source"),
                            "new_source": str(path),
                        }
                    )
                continue

            value = dict(passage)
            value["_source"] = str(path)

            library["passages"][reference] = value
            normalized_sources[normalized] = (
                reference,
                value,
            )

    if conflicts:
        print()
        print("ERROR: conflicting Bible passages found")
        for conflict in conflicts:
            print(conflict)
        raise SystemExit(2)

    return library


def main():
    files = source_files()
    library = build_library(files)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        yaml.safe_dump(
            library,
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    print()
    print("=== Bible Library ===")
    print(f"sources  : {len(files)}")
    print(f"passages : {len(library['passages'])}")
    print(f"output   : {OUTPUT}")

    for reference, value in (
        library["passages"].items()
    ):
        print(
            f"  {reference:<18} "
            f"<- {value['_source']}"
        )


if __name__ == "__main__":
    main()
