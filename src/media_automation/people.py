"""Confirmed person titles only; never assigns weekly roles or infers titles."""
CONFIRMED_TITLES = {
    '김한섭': '집사', '최진용': '형제', '이하선': '형제',
    '이광민': '형제', '장기훈': '형제', '이은철': '목사',
}

import json
import re
from pathlib import Path

PEOPLE_FILE = Path(__file__).resolve().parents[2] / 'data/private/people.json'
TITLES = {'형제','자매','집사','목사','사모','장로','권사'}


def confirmed_titles(path=None):
    path=Path(path) if path is not None else PEOPLE_FILE
    if not path.is_file():return dict(CONFIRMED_TITLES)
    payload=json.loads(path.read_text(encoding='utf-8'))
    people=payload.get('people')
    if payload.get('schema_version')!=1 or not isinstance(people,dict):raise ValueError('직분 명단 형식을 확인하세요.')
    if any(not isinstance(n,str) or not n.strip() or t not in TITLES for n,t in people.items()):raise ValueError('직분 명단의 이름과 직분을 확인하세요.')
    return {**CONFIRMED_TITLES,**people}


def format_people(value, titles=None):
    """Add only confirmed titles, preserve explicitly supplied titles and unknown names."""
    titles=confirmed_titles() if titles is None else titles
    parts=re.split(r'([,，\n])',str(value or ''))
    for i in range(0,len(parts),2):
        name=parts[i].strip()
        if name in titles:name+=' '+titles[name]
        parts[i]=name
    return ''.join(', ' if p in (',','，') else p for p in parts)
