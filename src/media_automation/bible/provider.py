from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BibleVerse:
    number: int
    text: str


@dataclass(frozen=True, slots=True)
class BiblePassage:
    reference: str
    verses: tuple[BibleVerse, ...]


class BiblePassageNotFoundError(LookupError):
    pass


class BibleProvider(Protocol):
    def get_passage(
        self,
        reference: str,
    ) -> BiblePassage:
        ...


class InMemoryBibleProvider:
    def __init__(
        self,
        passages: dict[
            str,
            BiblePassage,
        ],
    ) -> None:
        self._passages = dict(passages)

    def get_passage(
        self,
        reference: str,
    ) -> BiblePassage:
        passage = self._passages.get(
            reference
        )

        if passage is None:
            raise BiblePassageNotFoundError(
                f"등록된 성경 본문이 없습니다: "
                f"{reference}"
            )

        return passage
        