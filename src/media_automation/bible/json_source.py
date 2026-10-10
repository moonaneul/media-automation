"""Lookup user-supplied Bible JSON while preserving official combined verse units.

Friday Zoom consumes these units without splitting combined verse text.
Partial requests that cut through a combined unit raise CombinedVerseRangeError.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path


class CombinedVerseRangeError(ValueError):
    pass


def parse_reference(value: str):
    value = str(value).strip().replace('～', '~').replace('–', '~').replace('-', '~')
    m = re.fullmatch(r'([가-힣]+)\s*(\d+)\s*:\s*(\d+)(?:\s*~\s*(\d+))?', value)
    if not m:
        raise ValueError(f'성경 약어와 같은 장 범위가 필요합니다: {value}')
    from .master import normalize_book
    book, chapter, start = normalize_book(m[1]), int(m[2]), int(m[3])
    end = int(m[4] or start)
    if chapter < 1 or start < 1 or end < start:
        raise ValueError(f'장·절 범위가 잘못되었습니다: {value}')
    return book, chapter, start, end


def build_index(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError('JSON 최상위 객체가 필요합니다.')
    units = {}
    membership = {}
    for key, text in raw.items():
        b, ch, start, end = parse_reference(key)
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f'본문이 비어 있습니다: {key}')
        canonical = f'{b}{ch}:{start}' + (f'~{end}' if end != start else '')
        if canonical in units:
            raise ValueError(f'중복 본문 단위: {key}')
        units[canonical] = {
            'book': b, 'chapter': ch, 'start_verse': start, 'end_verse': end,
            'reference': f'{b} {ch}:{start}' + (f'~{end}' if end != start else ''),
            'text': text.strip(), 'combined': start != end,
        }
        for verse in range(start, end + 1):
            verse_key = f'{b}{ch}:{verse}'
            if verse_key in membership:
                raise ValueError(f'장·절 중복: {verse_key}')
            # A pointer to the combined unit; never a fabricated individual verse.
            membership[verse_key] = canonical
    return {'format_version': 1, 'units': units, 'verse_to_unit': membership}


def lookup(index: dict, reference: str) -> dict:
    b, ch, start, end = parse_reference(reference)
    selected = []
    seen = set()
    for verse in range(start, end + 1):
        key = f'{b}{ch}:{verse}'
        unit_key = index['verse_to_unit'].get(key)
        if unit_key is None:
            raise KeyError(f'자료에 장·절이 없습니다: {key}')
        unit = index['units'][unit_key]
        if unit['start_verse'] < start or unit['end_verse'] > end:
            raise CombinedVerseRangeError(
                f"{reference}는 개역개정 통합 절 {unit['reference']}의 일부입니다. "
                '본문을 임의 분리하지 않습니다. 통합 범위를 포함해 요청해 주세요.'
            )
        if unit_key not in seen:
            selected.append(dict(unit))
            seen.add(unit_key)
    return {'requested_reference': reference, 'units': selected}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bible', required=True)
    parser.add_argument('--reference', required=True)
    args = parser.parse_args()
    raw = json.loads(Path(args.bible).read_text(encoding='utf-8-sig'))
    print(json.dumps(lookup(build_index(raw), args.reference), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()


def split_references(value: str) -> list[str]:
    references = [part.strip() for part in re.split(r"[,，;；]", str(value))]
    if any(not part for part in references):
        raise ValueError(f"빈 성경 주소가 있습니다: {value}")
    for reference in references:
        parse_reference(reference)
    return references


def passage_from_json(index: dict, reference: str) -> dict:
    units = lookup(index, reference)["units"]
    return {
        "reference": reference,
        "verses": {unit["start_verse"]: unit["text"] for unit in units},
        "verse_ends": {
            unit["start_verse"]: unit["end_verse"]
            for unit in units if unit["combined"]
        },
        "source_note": "user-provided JSON; full text comparison not completed",
    }
