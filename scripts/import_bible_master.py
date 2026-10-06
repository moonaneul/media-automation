from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "private" / "bible_master.yaml"


def load_input(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"성경 마스터 파일을 찾을 수 없습니다: {path}")

    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8-sig"))

    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}

    raise ValueError("현재 성경 마스터 입력은 YAML 또는 JSON을 지원합니다.")


def positive_int(value, *, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} 번호가 정수가 아닙니다: {value}") from error
    if number < 1:
        raise ValueError(f"{label} 번호는 1 이상이어야 합니다: {value}")
    return number


def normalize_master(raw: dict) -> dict:
    if raw.get("translation") != "개역개정":
        raise ValueError("translation은 반드시 '개역개정'이어야 합니다.")

    books = raw.get("books")
    if not isinstance(books, dict) or not books:
        raise ValueError("books 객체가 필요합니다.")

    clean_books: dict[str, dict[int, dict[int, str]]] = {}
    for raw_book, raw_chapters in books.items():
        book = str(raw_book).strip()
        if not book:
            raise ValueError("빈 성경 책 이름이 있습니다.")
        if not isinstance(raw_chapters, dict) or not raw_chapters:
            raise ValueError(f"장 데이터가 없습니다: {book}")

        chapters: dict[int, dict[int, str]] = {}
        for raw_chapter, raw_verses in raw_chapters.items():
            chapter = positive_int(raw_chapter, label=f"{book} 장")
            if not isinstance(raw_verses, dict) or not raw_verses:
                raise ValueError(f"절 데이터가 없습니다: {book} {chapter}장")

            verses: dict[int, str] = {}
            for raw_verse, raw_text in raw_verses.items():
                verse = positive_int(raw_verse, label=f"{book} {chapter}장 절")
                if not isinstance(raw_text, str) or not raw_text.strip():
                    raise ValueError(f"본문이 비어 있습니다: {book} {chapter}:{verse}")
                if verse in verses:
                    raise ValueError(f"절 번호가 중복되었습니다: {book} {chapter}:{verse}")
                verses[verse] = raw_text.strip()

            chapters[chapter] = dict(sorted(verses.items()))

        clean_books[book] = dict(sorted(chapters.items()))

    return {
        "translation": "개역개정",
        "validated": True,
        "source_note": "user-provided verified Bible master",
        "books": clean_books,
    }


def summarize(master: dict) -> tuple[int, int, int]:
    books = master.get("books", {})
    book_count = len(books)
    chapter_count = sum(len(chapters) for chapters in books.values())
    verse_count = sum(
        len(verses)
        for chapters in books.values()
        for verses in chapters.values()
    )
    return book_count, chapter_count, verse_count


def main():
    parser = argparse.ArgumentParser(description="검증된 개역개정 전체 성경 마스터 등록")
    parser.add_argument("input")
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()

    source = Path(args.input)
    if not source.is_absolute():
        source = ROOT / source

    master = normalize_master(load_input(source))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists() and not args.replace:
        existing = yaml.safe_load(OUTPUT.read_text(encoding="utf-8-sig")) or {}
        if existing == master:
            print(f"BIBLE MASTER: 이미 같은 내용으로 등록됨: {OUTPUT}")
            return
        raise SystemExit(
            "ERROR: 기존 Bible master가 있습니다. 자동 덮어쓰지 않습니다.\n"
            "교체가 의도된 경우에만 --replace를 사용하세요.\n"
            f"existing: {OUTPUT}"
        )

    OUTPUT.write_text(
        yaml.safe_dump(master, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    books, chapters, verses = summarize(master)
    print("\n=== Bible Master Registered ===")
    print("translation : 개역개정")
    print(f"books       : {books}")
    print(f"chapters    : {chapters}")
    print(f"verses      : {verses}")
    print(f"output      : {OUTPUT}")
    if books != 66:
        print("WARNING: 66권 전체가 아닙니다. 일부 본문 요청은 계속 중단될 수 있습니다.")


if __name__ == "__main__":
    main()
