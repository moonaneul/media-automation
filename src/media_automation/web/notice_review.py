"""Reviewable, lossless *draft* of weekly notices (not a worship content approval).

The existing service-specific parsers remain the only interpretation source. This
module layers explicit corrections over a single week's first notice. It never
reads earlier jobs and never fills a missing/blank field with older data.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import yaml

from .inputs import OPERATIONAL

ROOT = {'sunday': 'sunday', 'wednesday': 'wednesday', 'friday': 'friday_zoom'}
SCRIPT = {'sunday': 'parse_sunday_notice.py',
          'wednesday': 'parse_wednesday_notice.py',
          'friday': 'parse_friday_zoom_notice.py'}
STATES = {'provided': 'VALUE', 'asset_required': 'VALUE',
          'blank': 'NONE', 'missing': 'UNSET'}


def _parser(workspace: Path, service: str):
    script = workspace / 'scripts' / SCRIPT[service]
    if not script.is_file():
        raise ValueError('이번 작업에 예배별 안내 파서가 없습니다. 코드 스냅샷을 확인해주세요.')
    spec = spec_from_file_location('weekly_notice_preview_' + service, script)
    if spec is None or spec.loader is None:
        raise ValueError('안내 파서를 읽지 못했습니다.')
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse(module, service: str, text: str, date: str):
    if service == 'friday':
        return module.parse_notice(text, reference_year=int(date[:4]))
    return module.parse_notice(text)


def preview(workspace: Path, service: str, date: str) -> dict:
    if service not in ROOT:
        return {'available': False, 'note': '주보는 같은 주 주일 안내 해석 자료를 별도 등록합니다.'}
    root = ROOT[service]
    prefix = f'input/{root}/{date.replace("-", "")}/notices'
    initial = workspace / prefix / 'initial.txt'
    if not initial.is_file():
        return {'available': False, 'note': '이번 주 예배 안내 TXT를 먼저 등록해주세요.'}
    module = _parser(workspace, service)
    initial_text = initial.read_text(encoding='utf-8-sig')
    data, unknown = _parse(module, service, initial_text, date)
    sources = [{'path': f'{prefix}/initial.txt',
                'sha256': hashlib.sha256(initial.read_bytes()).hexdigest()}]
    origin = {key: sources[0]['path'] for key, value in data.items()
              if value.get('status') != 'missing'}
    review = [{'source': sources[0]['path'], 'line': line} for line in unknown]
    checks = []
    for revision in sorted(initial.parent.glob('revision_*.txt')):
        name = revision.relative_to(workspace).as_posix()
        source_text = revision.read_text(encoding='utf-8-sig')
        sources.append({'path': name, 'sha256': hashlib.sha256(revision.read_bytes()).hexdigest()})
        # A song count is a multi-field instruction. When written as a correction
        # without its original service context, refuse to infer which fields it
        # replaces. An explicit per-slot correction is safe to merge.
        if service in {'sunday', 'wednesday'}:
            for line in source_text.splitlines():
                if not line.strip():
                    continue
                label = module.split_label(line)
                if label is not None and label[0] == 'song_count':
                    review.append({'source': name, 'line': line.strip(),
                                   'reason': '수정 안내의 찬양 곡 수는 다중 항목 변경이므로 수동 검토가 필요합니다.'})
        changed, unexpected = _parse(module, service, source_text, date)
        review.extend({'source': name, 'line': line} for line in unexpected)
        if service == 'friday':
            # The Friday parser supplies a fixed personal-prayer step by policy.
            # It is not a new correction if this revision never mentioned it.
            explicit_personal_prayer = any('개인 기도' in line or '개인기도' in line
                                           for line in source_text.splitlines())
        else:
            explicit_personal_prayer = True
        for key, record in changed.items():
            if record.get('status') == 'missing':
                continue
            if key == 'personal_prayer' and not explicit_personal_prayer:
                continue
            # Reject ambiguous multi-target song-count revisions as a whole;
            # never silently apply even their inferred blank statuses.
            if service in {'sunday', 'wednesday'} and any(
                item['source'] == name and '다중 항목' in item.get('reason', '') for item in review
            ):
                continue
            data[key] = deepcopy(record)
            origin[key] = name

    date_record = data.get('date', {})
    if date_record.get('status') != 'provided' or str(date_record.get('value')) != date:
        checks.append('안내의 날짜가 미제공 또는 작업 날짜와 다릅니다. 작업 날짜를 임의로 보충하지 않습니다.')
    fields = []
    for name in OPERATIONAL[service]:
        record = data.get(name, {'status': 'missing', 'value': None})
        state = STATES.get(record.get('status'), 'UNSET')
        fields.append({'name': name, 'state': state, 'value': record.get('value'),
                       'source': origin.get(name),
                       'asset_required': record.get('status') == 'asset_required'})
        if state == 'UNSET':
            checks.append(f'{name}: 이번 주 안내에 값이 전달되지 않았습니다(UNSET).')
        if state == 'NONE' and name in {'scripture', 'sermon_title'}:
            checks.append(f'{name}: 필수 항목이 명시적으로 없음(NONE)입니다.')
        if record.get('review_required'):
            checks.append(f'{name}: 기존 파서가 수동 검토를 요구합니다.')
    if review:
        checks.append('인식하지 못한 문장 또는 모호한 수정 지시가 있습니다. 원문 검토가 필요합니다.')
    return {'available': True, 'service': service, 'date': date,
            'date_state': STATES.get(date_record.get('status'), 'UNSET'),
            'date_value': date_record.get('value'), 'fields': fields,
            'sources': sources, 'review_items': review, 'checks': checks,
            'can_confirm': not checks, '_records': data}


def confirmed_yaml(draft: dict) -> bytes:
    if not draft['available'] or not draft['can_confirm']:
        raise ValueError('안내의 미확인 항목과 수정 지시를 먼저 확인해주세요.')
    records = draft['_records']
    result = {'service': 'friday_zoom' if draft['service'] == 'friday' else draft['service'],
              'review_required': False, 'review_items': [],
              'date': records['date'],
              'fields': {key: value for key, value in records.items() if key != 'date'},
              'web_review': {'confirmed_sources': draft['sources'],
                             'confirmation': '운영자가 웹 화면에서 안내 해석을 확인함',
                             'content_qa': 'NOT_VERIFIED'}}
    return yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode('utf-8')
