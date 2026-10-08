from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

import yaml

from media_automation.bible.json_source import (
    build_index, passage_from_json, split_references,
)
from media_automation.bible.master import extract_same_chapter_passage


def normalize_reference(value: str) -> str:
    return str(value).strip().replace('-', '~').replace('～', '~')


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding='utf-8-sig')) or {}


def resolve_requests(requests: dict, library: dict, master: dict, json_index: dict | None = None):
    lookup = {
        normalize_reference(key): value
        for key, value in library.get('passages', {}).items()
    }
    resolved, missing = {}, []
    for item in requests.get('requests', []):
        if not item.get('reference'):
            continue
        try:
            references = split_references(item['reference'])
        except ValueError as error:
            missing.append((str(item['reference']), str(error)))
            continue
        for reference in references:
            if reference in resolved:
                continue
            clean = lookup.get(normalize_reference(reference))
            if clean is not None:
                clean = copy.deepcopy(clean)
                clean.pop('_source', None)
                resolved[reference] = clean
                continue
            # A configured JSON is never silently replaced with inferred text.
            if json_index is not None:
                try:
                    resolved[reference] = passage_from_json(json_index, reference)
                except (ValueError, KeyError) as error:
                    missing.append((reference, str(error)))
                continue
            try:
                if not master:
                    raise KeyError('전체 성경 JSON 또는 검증된 Bible master가 없습니다.')
                resolved[reference] = extract_same_chapter_passage(master, reference)
            except (ValueError, KeyError) as error:
                missing.append((reference, str(error)))
    return resolved, missing


def main():
    parser = argparse.ArgumentParser(description='금요 Zoom 개역개정 성경 조회')
    parser.add_argument('--requests', required=True)
    parser.add_argument('--library', default='data/bible_library.yaml')
    parser.add_argument('--master', default='data/private/bible_master.yaml')
    parser.add_argument('--json-bible', default='data/private/bible_fixed.json')
    parser.add_argument('--output')
    args = parser.parse_args()
    request_path = Path(args.requests)
    if not request_path.exists():
        raise SystemExit(f'ERROR: requests file missing: {request_path}')
    source_path = Path(args.json_bible)
    json_index = None
    if source_path.exists():
        raw = json.loads(source_path.read_text(encoding='utf-8-sig'))
        json_index = build_index(raw)
    resolved, missing = resolve_requests(
        load_yaml(request_path), load_yaml(Path(args.library)),
        load_yaml(Path(args.master)), json_index,
    )
    if missing:
        print('\nBIBLE RESOLVE: NOT READY')
        for reference, reason in missing:
            print(f'MISSING: {reference}\n  reason: {reason}')
        print('본문을 임의 생성하거나 다른 번역본으로 대체하지 않습니다.')
        raise SystemExit(2)
    token = request_path.stem.replace('friday_zoom_', '').replace('_bible_requests', '')
    output = Path(args.output) if args.output else Path('output/friday_zoom_intake') / f'friday-zoom-{token}-bible.yaml'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(yaml.safe_dump({'passages': resolved}, allow_unicode=True, sort_keys=False), encoding='utf-8')
    print('\nBIBLE RESOLVE: PASS')
    for reference in resolved:
        print(f'OK: {reference}')
    if json_index is not None:
        print(f'JSON source: {source_path} (전체 본문 대조 검수와는 별도)')
    print(f'output: {output}')


if __name__ == '__main__':
    main()
