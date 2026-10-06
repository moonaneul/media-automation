from pathlib import Path
import yaml


SOURCE_DIR = Path("samples/weekly")
OUTPUT = Path("data/bible_library.yaml")

files = sorted(
    SOURCE_DIR.glob("*-bible.yaml")
)

library = {
    "translation": "개역개정",
    "passages": {},
}

conflicts = []

for path in files:
    raw = yaml.safe_load(
        path.read_text(
            encoding="utf-8-sig"
        )
    ) or {}

    passages = raw.get(
        "passages",
        {}
    )

    for reference, passage in passages.items():
        existing = library[
            "passages"
        ].get(reference)

        if (
            existing is not None
            and existing != passage
        ):
            conflicts.append(
                {
                    "reference": reference,
                    "existing_source":
                        existing.get("_source"),
                    "new_source":
                        str(path),
                }
            )
            continue

        value = dict(passage)

        value["_source"] = str(
            path
        )

        library[
            "passages"
        ][reference] = value


if conflicts:
    print()
    print(
        "ERROR: conflicting Bible passages found"
    )

    for conflict in conflicts:
        print(
            conflict
        )

    raise SystemExit(2)


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
print(
    f"sources  : {len(files)}"
)
print(
    f"passages : "
    f"{len(library['passages'])}"
)
print(
    f"output   : {OUTPUT}"
)

for reference, value in (
    library["passages"].items()
):
    print(
        f"  {reference:<18} "
        f"<- {value['_source']}"
    )
