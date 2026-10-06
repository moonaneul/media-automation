from __future__ import annotations

from dataclasses import dataclass
import re


BOOK_ALIASES = {
    "창": "창", "창세기": "창",
    "출": "출", "출애굽기": "출",
    "레": "레", "레위기": "레",
    "민": "민", "민수기": "민",
    "신": "신", "신명기": "신",
    "수": "수", "여호수아": "수",
    "삿": "삿", "사사기": "삿",
    "룻": "룻", "룻기": "룻",
    "삼상": "삼상", "사무엘상": "삼상",
    "삼하": "삼하", "사무엘하": "삼하",
    "왕상": "왕상", "열왕기상": "왕상",
    "왕하": "왕하", "열왕기하": "왕하",
    "대상": "대상", "역대상": "대상",
    "대하": "대하", "역대하": "대하",
    "스": "스", "에스라": "스",
    "느": "느", "느헤미야": "느",
    "에": "에", "에스더": "에",
    "욥": "욥", "욥기": "욥",
    "시": "시", "시편": "시",
    "잠": "잠", "잠언": "잠",
    "전": "전", "전도서": "전",
    "아": "아", "아가": "아",
    "사": "사", "이사야": "사",
    "렘": "렘", "예레미야": "렘",
    "애": "애", "예레미야애가": "애",
    "겔": "겔", "에스겔": "겔",
    "단": "단", "다니엘": "단",
    "호": "호", "호세아": "호",
    "욜": "욜", "요엘": "욜",
    "암": "암", "아모스": "암",
    "옵": "옵", "오바댜": "옵",
    "욘": "욘", "요나": "욘",
    "미": "미", "미가": "미",
    "나": "나", "나훔": "나",
    "합": "합", "하박국": "합",
    "습": "습", "스바냐": "습",
    "학": "학", "학개": "학",
    "슥": "슥", "스가랴": "슥",
    "말": "말", "말라기": "말",
    "마": "마", "마태복음": "마",
    "막": "막", "마가복음": "막",
    "눅": "눅", "누가복음": "눅",
    "요": "요", "요한복음": "요",
    "행": "행", "사도행전": "행",
    "롬": "롬", "로마서": "롬",
    "고전": "고전", "고린도전서": "고전",
    "고후": "고후", "고린도후서": "고후",
    "갈": "갈", "갈라디아서": "갈",
    "엡": "엡", "에베소서": "엡",
    "빌": "빌", "빌립보서": "빌",
    "골": "골", "골로새서": "골",
    "살전": "살전", "데살로니가전서": "살전",
    "살후": "살후", "데살로니가후서": "살후",
    "딤전": "딤전", "디모데전서": "딤전",
    "딤후": "딤후", "디모데후서": "딤후",
    "딛": "딛", "디도서": "딛",
    "몬": "몬", "빌레몬서": "몬",
    "히": "히", "히브리서": "히",
    "약": "약", "야고보서": "약",
    "벧전": "벧전", "베드로전서": "벧전",
    "벧후": "벧후", "베드로후서": "벧후",
    "요일": "요일", "요한일서": "요일",
    "요이": "요이", "요한이서": "요이",
    "요삼": "요삼", "요한삼서": "요삼",
    "유": "유", "유다서": "유",
    "계": "계", "요한계시록": "계",
}


@dataclass(frozen=True, slots=True)
class ParsedReference:
    book: str
    chapter: int
    start_verse: int
    end_chapter: int
    end_verse: int

    @property
    def crosses_chapters(self) -> bool:
        return self.chapter != self.end_chapter


def normalize_book(value: str) -> str:
    key = re.sub(r"\s+", "", str(value).strip())
    canonical = BOOK_ALIASES.get(key)
    if canonical is None:
        raise ValueError(f"지원하지 않는 성경 책 표기입니다: {value}")
    return canonical


def parse_reference(value: str) -> ParsedReference:
    normalized = (
        str(value)
        .strip()
        .replace("-", "~")
        .replace("～", "~")
    )
    match = re.fullmatch(
        r"(.+?)\s*(\d+)\s*:\s*(\d+)(?:\s*~\s*(?:(\d+)\s*:\s*)?(\d+))?",
        normalized,
    )
    if not match:
        raise ValueError(f"성경 본문 범위를 해석할 수 없습니다: {value}")

    book = normalize_book(match.group(1))
    chapter = int(match.group(2))
    start_verse = int(match.group(3))
    end_chapter = int(match.group(4) or chapter)
    end_verse = int(match.group(5) or start_verse)

    if chapter < 1 or start_verse < 1 or end_chapter < 1 or end_verse < 1:
        raise ValueError(f"성경 장·절은 1 이상이어야 합니다: {value}")
    if end_chapter < chapter:
        raise ValueError(f"성경 범위 순서가 잘못되었습니다: {value}")
    if end_chapter == chapter and end_verse < start_verse:
        raise ValueError(f"성경 절 범위 순서가 잘못되었습니다: {value}")

    return ParsedReference(
        book=book,
        chapter=chapter,
        start_verse=start_verse,
        end_chapter=end_chapter,
        end_verse=end_verse,
    )


def normalize_master_books(raw_books: dict) -> dict[str, dict[int, dict[int, str]]]:
    if not isinstance(raw_books, dict):
        raise ValueError("Bible master의 books 객체가 필요합니다.")

    clean: dict[str, dict[int, dict[int, str]]] = {}
    for raw_book, raw_chapters in raw_books.items():
        book = normalize_book(str(raw_book))
        if not isinstance(raw_chapters, dict):
            raise ValueError(f"장 데이터가 잘못되었습니다: {raw_book}")
        if book in clean:
            raise ValueError(f"같은 성경 책이 중복되었습니다: {raw_book}")

        chapters: dict[int, dict[int, str]] = {}
        for raw_chapter, raw_verses in raw_chapters.items():
            chapter = int(raw_chapter)
            if chapter < 1 or not isinstance(raw_verses, dict):
                raise ValueError(f"장 데이터가 잘못되었습니다: {raw_book} {raw_chapter}")

            verses: dict[int, str] = {}
            for raw_verse, raw_text in raw_verses.items():
                verse = int(raw_verse)
                text = str(raw_text).strip() if isinstance(raw_text, str) else ""
                if verse < 1 or not text:
                    raise ValueError(f"본문이 비어 있거나 절 번호가 잘못되었습니다: {raw_book} {chapter}:{raw_verse}")
                verses[verse] = text
            chapters[chapter] = dict(sorted(verses.items()))

        clean[book] = dict(sorted(chapters.items()))

    return clean


def extract_same_chapter_passage(master: dict, reference: str) -> dict:
    if master.get("translation") != "개역개정":
        raise ValueError("Bible master는 반드시 개역개정이어야 합니다.")
    if master.get("validated") is not True:
        raise ValueError("검증 완료된 Bible master만 사용할 수 있습니다.")

    parsed = parse_reference(reference)
    if parsed.crosses_chapters:
        raise ValueError(
            "현재 예배 PPT 본문 모델은 장을 넘는 범위를 아직 지원하지 않습니다: "
            f"{reference}"
        )

    books = normalize_master_books(master.get("books", {}))
    chapters = books.get(parsed.book)
    if chapters is None:
        raise KeyError(f"Bible master에 책이 없습니다: {parsed.book}")
    verses = chapters.get(parsed.chapter)
    if verses is None:
        raise KeyError(f"Bible master에 장이 없습니다: {parsed.book} {parsed.chapter}장")

    selected = {}
    missing = []
    for number in range(parsed.start_verse, parsed.end_verse + 1):
        text = verses.get(number)
        if text is None:
            missing.append(number)
        else:
            selected[number] = text

    if missing:
        raise KeyError(
            f"Bible master에 절이 없습니다: {reference} / {missing}"
        )

    display = reference.replace("-", "~").replace("～", "~")
    return {
        "reference": display,
        "verses": selected,
    }
