from __future__ import annotations

from pathlib import Path

from media_automation.bible import BiblePassage

from .in_person_qa import (
    InPersonQaIssue,
    InPersonQaResult,
    validate_in_person_structure,
)
from .wednesday_structure import (
    WednesdaySlideRange,
)


WednesdayQaIssue = InPersonQaIssue
WednesdayQaResult = InPersonQaResult


def validate_wednesday_structure(
    presentation_path: str | Path,
    *,
    slide_ranges: dict[
        str,
        WednesdaySlideRange,
    ],
    scripture_passages: dict[
        str,
        BiblePassage,
    ] | None = None,
) -> WednesdayQaResult:
    return validate_in_person_structure(
        presentation_path,
        slide_ranges=slide_ranges,
        scripture_passages=scripture_passages,
    )