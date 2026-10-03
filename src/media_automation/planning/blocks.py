from dataclasses import dataclass
from enum import Enum
from typing import Any


class BlockKind(str, Enum):
    PRE_SERVICE = "pre_service"

    SONG = "song"
    ZOOM_SONG = "zoom_song"

    PRAYER = "prayer"
    PRAYER_TOPICS = "prayer_topics"
    PERSONAL_PRAYER = "personal_prayer"

    CHURCH_NEWS = "church_news"
    SCRIPTURE = "scripture"
    SERMON_TITLE = "sermon_title"
    BLANK = "blank"


@dataclass(frozen=True, slots=True)
class SermonTitleContent:
    title: str
    scripture_reference: str


@dataclass(frozen=True, slots=True)
class WorshipBlock:
    """
    PPT를 만들기 전 단계의 예배 순서 단위.

    key:
        Weekly Data 안에서 이 블록의 의미/출처를 식별한다.

    value:
        실제 Song, ScriptureField, PersonField 등의 데이터.
        blank / pre_service는 None일 수 있다.
    """

    kind: BlockKind
    key: str
    value: Any = None