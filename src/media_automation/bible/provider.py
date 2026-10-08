from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class BibleVerse:
    number: int
    text: str
    end_number: int | None = None

    @property
    def display_number(self) -> str:
        if self.end_number is not None and self.end_number != self.number:
            return f"{self.number}~{self.end_number}"
        return str(self.number)


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
        