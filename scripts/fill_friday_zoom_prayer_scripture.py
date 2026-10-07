from __future__ import annotations

import argparse
from pathlib import Path
import yaml
from media_automation.bible.json_source import split_references


def fill_prayer_scripture(intake: dict, bible: dict) -> int:
    count = 0
    for field in ('first_prayer', 'word_prayer', 'community_prayer', 'personal_prayer'):
        record = intake['fields'][field]
        if record['status'] != 'provided':
            continue
        values = record['value']
        scalar = isinstance(values, str)
        if scalar:
            values = [values]
        updated = []
        for value in values:
            lines = []
            for line in value.splitlines():
                try:
                    refs = split_references(line.strip())
                except ValueError:
                    lines.append(line)
                    continue
                for reference in refs:
                    passage = bible['passages'][reference]
                    ends = passage.get('verse_ends', {})
                    text = ' '.join(
                        f"[{number}~{ends[number]}] {body}" if number in ends else f"[{number}] {body}"
                        for number, body in passage['verses'].items()
                    )
                    lines.append(f'{text} ({reference})')
                count += 1
            updated.append('\n'.join(lines))
        record['value'] = updated[0] if scalar else updated
    return count


def main():
    parser = argparse.ArgumentParser(description='기도에 성경 주소만 적힌 줄의 본문 채우기')
    parser.add_argument('--intake', required=True)
    parser.add_argument('--bible', required=True)
    args = parser.parse_args()
    path = Path(args.intake)
    intake = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
    bible = yaml.safe_load(Path(args.bible).read_text(encoding='utf-8-sig'))
    count = fill_prayer_scripture(intake, bible)
    path.write_text(yaml.safe_dump(intake, allow_unicode=True, sort_keys=False), encoding='utf-8')
    print(f'PRAYER SCRIPTURE: filled {count} reference-only lines')


if __name__ == '__main__':
    main()
