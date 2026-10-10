"""Explicit same-week Sunday data handoff, no cross-week or silent inheritance."""
from __future__ import annotations

from pathlib import Path

import yaml

from .inputs import _read_yaml, inspect_intake

COMMON = ('scripture', 'sermon_title', 'second_service_prayer',
          'second_service_offering_prayer', 'church_news', 'additional_scripture')


def shared_paths(date: str) -> dict[str, str]:
    d = date.replace('-', '')
    return {
        'sunday_intake': f'output/sunday_intake/sunday_{d}_intake.yaml',
        'sunday_base': f'output/sunday_intake/sunday-{d}-base.yaml',
        'sunday_weekly': f'output/sunday_intake/sunday-{d}.yaml',
    }


def summary(workspace: Path, date: str) -> dict:
    paths = shared_paths(date)
    intake = workspace / paths['sunday_intake']
    if not intake.is_file():
        return {'available': False, 'fields': [], 'checks': [],
                'note': '같은 주의 검토된 주일 안내 해석 YAML을 등록하거나 가져와야 합니다.'}
    raw = _read_yaml(intake)
    fields, checks = inspect_intake(intake, date, 'sunday')
    if raw is None:
        return {'available': True, 'fields': [], 'checks': checks, 'consistent': False}
    output = []
    records = raw.get('fields') if isinstance(raw.get('fields'), dict) else {}
    for item in fields:
        if item['name'] not in COMMON:
            continue
        record = records.get(item['name'], {})
        output.append({'name': item['name'], 'state': item['state'],
                       'value': record.get('value') if isinstance(record, dict) else None})
    for kind in ('sunday_base', 'sunday_weekly'):
        path = workspace / paths[kind]
        if path.is_file():
            data = _read_yaml(path)
            if data is None or str(data.get('date')) != date or data.get('service') != 'sunday':
                checks.append(f'{kind}: 같은 주 주일 데이터의 날짜 또는 종류가 맞지 않습니다.')
            elif kind == 'sunday_weekly':
                worship = data.get('worship', {})
                for field, prop in (('sermon_title', 'text'), ('scripture', 'reference')):
                    explicit = records.get(field, {})
                    if explicit.get('status') != 'provided':
                        continue
                    weekly = worship.get(field, {})
                    if not isinstance(weekly, dict) or weekly.get('status') != 'VALUE' or (str(weekly.get(prop, '')).strip()
                        != str(explicit.get('value', '')).strip()):
                        checks.append(f'{field}: 주일 안내와 주간 통합 YAML의 값이 다릅니다.')
    return {'available': True, 'fields': output, 'checks': checks,
            'consistent': not checks,
            'note': '같은 주 주일 안내의 공통 값입니다. 전달 주보 질문/광고 및 실제 PDF 교차검수는 별도 단계입니다.'}
