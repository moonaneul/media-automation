"""Explicit per-service web intake paths and conservative preflight checks.

Presence is not validation of content, permission, score correctness or playback.
The raw notice is not treated as an already parsed operational intake.
"""
from __future__ import annotations

import re
import hashlib
from pathlib import Path

import yaml

KINDS = {
    'sunday': [
        ('notice', '이번 주 예배 안내', ['.txt'], None),
        ('revision', '추가·수정 안내', ['.txt'], None),
        ('transfer', '전달 주보', ['.hwp', '.hwpx', '.txt'], None),
        ('source', '예배 전 안내 원본 PPTX', ['.pptx'], None),
        ('score', '검수된 악보 PPTX', ['.pptx'], ['opening_song_1', 'opening_song_2', 'opening_song_3', 'separate_hymn', 'offering_hymn', 'special_song', 'decision_hymn']),
        ('intake', '검토된 주일 안내 해석 YAML', ['.yaml', '.yml'], None),
        ('bible', '개역개정 본문 데이터', ['.json'], None),
    ],
    'bulletin': [
        ('transfer', '이번 주 전달 주보', ['.hwp', '.hwpx', '.txt'], None),
        ('sunday_intake', '같은 주 주일 안내 해석 YAML', ['.yaml', '.yml'], None),
        ('sunday_base', '같은 주 주일 기본 데이터 YAML', ['.yaml', '.yml'], None),
        ('sunday_weekly', '같은 주 주일 통합 데이터 YAML', ['.yaml', '.yml'], None),
    ],
    'wednesday': [
        ('notice', '이번 주 예배 안내', ['.txt'], None),
        ('revision', '추가·수정 안내', ['.txt'], None),
        ('source', '수요예배 원본 PPTX', ['.pptx'], None),
        ('score', '검수된 악보 PPTX', ['.pptx'], ['opening_song_1', 'opening_song_2', 'opening_song_3', 'additional_song', 'decision_hymn']),
        ('intake', '검토된 수요 안내 해석 YAML', ['.yaml', '.yml'], None),
        ('bible', '개역개정 본문 데이터', ['.json'], None),
    ],
    'friday': [
        ('notice', '이번 주 Zoom 예배 안내', ['.txt'], None),
        ('revision', '추가·수정 안내', ['.txt'], None),
        ('zoom_reference', 'Zoom PPT 참고 원본 (자동 병합 안 함)', ['.pptx'], None),
        ('media', '이번 주 지정 영상·음원', ['.mp4', '.mp3'], ['opening_song_1', 'opening_song_2', 'first_prayer', 'song_after_prayer', 'response_song', 'word_prayer', 'intercession_song', 'community_prayer', 'personal_prayer', 'pre_service_audio']),
        ('intake', '검토된 금요 안내 해석 YAML', ['.yaml', '.yml'], None),
        ('weekly', '금요 주간 데이터 YAML', ['.yaml', '.yml'], None),
        ('scripture', '검증된 본문 YAML', ['.yaml', '.yml'], None),
        ('checklist', '금요 미디어 체크리스트 YAML', ['.yaml', '.yml'], None),
    ],
}

VIDEO_SLOTS = {'opening_song_1', 'opening_song_2', 'song_after_prayer', 'response_song', 'intercession_song'}
OPERATIONAL = {
    'sunday': ('opening_song_1', 'opening_song_2', 'opening_song_3', 'separate_hymn', 'second_service_prayer', 'church_news', 'offering_hymn', 'second_service_offering_prayer', 'special_song', 'sermon_title', 'scripture', 'additional_scripture', 'decision_hymn'),
    'wednesday': ('opening_song_1', 'opening_song_2', 'opening_song_3', 'prayer', 'additional_song', 'scripture', 'sermon_title', 'additional_scripture', 'decision_hymn'),
    'friday': ('opening_song_1', 'opening_song_2', 'first_prayer', 'song_after_prayer', 'scripture', 'sermon_title', 'additional_scripture', 'response_song', 'word_prayer', 'intercession_song', 'community_prayer', 'personal_prayer'),
}


def catalog(service: str) -> list[dict]:
    if service not in KINDS:
        raise ValueError('지원하지 않는 예배 종류입니다.')
    return [{'kind': kind, 'label': label, 'extensions': ext, 'slots': slots or []}
            for kind, label, ext, slots in KINDS[service]]


def typed_path(service: str, date: str, kind: str, filename: str, slot: str | None = None) -> str:
    match = next((row for row in KINDS[service] if row[0] == kind), None)
    if match is None:
        raise ValueError('현재 예배에서 사용할 수 없는 자료 유형입니다.')
    _, _, extensions, slots = match
    if not filename or Path(filename).name != filename or '\\' in filename or len(filename) > 180 or '\x00' in filename:
        raise ValueError('파일 이름을 확인해주세요.')
    ext = Path(filename).suffix.lower()
    if ext not in extensions:
        raise ValueError(f'이 자료는 {", ".join(extensions)} 파일만 받습니다.')
    if slots:
        if slot not in slots:
            raise ValueError('허용되지 않은 자료 슬롯입니다.')
    elif slot:
        raise ValueError('이 자료에는 슬롯을 선택하지 않습니다.')
    d = date.replace('-', '')
    if kind == 'transfer':
        return f'input/bulletin/{d}/transfer{ext}'
    if kind == 'notice':
        root = 'friday_zoom' if service == 'friday' else service
        return f'input/{root}/{d}/notices/initial.txt'
    if kind == 'revision':
        # Caller assigns a unique revision name; never overwrites the previous instruction.
        raise ValueError('수정 안내는 순차 번호가 필요합니다.')
    if kind == 'source':
        return f'input/{service}/{d}/source_rehearsal.pptx'
    if kind == 'zoom_reference':
        return f'input/friday_zoom/{d}/reference.pptx'
    if kind == 'score':
        return f'input/{service}/{d}/{slot}.pptx'
    if kind == 'media':
        required_ext = '.mp4' if slot in VIDEO_SLOTS else '.mp3'
        if ext != required_ext:
            raise ValueError(f'{slot} 슬롯에는 {required_ext} 자료가 필요합니다.')
        return f'input/friday_zoom/{d}/{slot}{ext}'
    if kind == 'bible':
        return 'data/private/bible_fixed.json'
    if kind in ('intake', 'sunday_intake'):
        prefix = 'sunday' if kind == 'sunday_intake' else ('friday_zoom' if service == 'friday' else service)
        folder = 'friday_zoom' if service == 'friday' else prefix
        return f'output/{folder}_intake/{prefix}_{d}_intake.yaml'
    if kind in ('sunday_base', 'sunday_weekly'):
        return f'output/sunday_intake/sunday-{d}{"-base" if kind == "sunday_base" else ""}.yaml'
    if kind in ('weekly', 'scripture', 'checklist'):
        if kind == 'checklist':
            return f'output/friday_zoom_intake/friday_zoom_{d}_media_checklist.yaml'
        return f'output/friday_zoom_intake/friday-zoom-{d}{"-bible" if kind == "scripture" else ""}.yaml'
    raise ValueError('잘못된 자료 유형입니다.')


def next_revision_path(workspace: Path, service: str, date: str) -> str:
    d = date.replace('-', '')
    root = 'friday_zoom' if service == 'friday' else service
    for n in range(1, 1000):
        relative = f'input/{root}/{d}/notices/revision_{n:03}.txt'
        if not (workspace / relative).exists():
            return relative
    raise ValueError('추가 지시가 너무 많습니다.')


def _read_yaml(path: Path):
    try:
        result = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
        return result if isinstance(result, dict) else None
    except (OSError, ValueError, yaml.YAMLError):
        return None


def inspect_intake(path: Path, date: str, service: str) -> tuple[list[dict], list[str]]:
    """Only interpret explicit parser statuses; do not infer missing or blank values."""
    raw = _read_yaml(path)
    if raw is None:
        return [], ['안내 해석 YAML을 읽을 수 없습니다.']
    errors = []
    parsed_date = raw.get('date')
    if not isinstance(parsed_date, dict) or parsed_date.get('status') != 'provided' or str(parsed_date.get('value')) != date:
        errors.append('안내 해석 YAML에 이번 작업 날짜가 명시적으로 확인되지 않았습니다.')
    if raw.get('review_required'):
        errors.append('안내 문장 REVIEW 처리가 남아 있습니다.')
    fields = raw.get('fields', {})
    if not isinstance(fields, dict):
        return [], errors + ['안내 해석 YAML의 fields가 올바르지 않습니다.']
    result = []
    for name in OPERATIONAL[service]:
        record = fields.get(name, {})
        status = record.get('status') if isinstance(record, dict) else None
        state = {'provided':'VALUE','asset_required':'VALUE','blank':'NONE','missing':'UNSET'}.get(status, 'UNSET')
        result.append({'name': name, 'state': state})
        if state == 'UNSET':
            errors.append(f'{name}: 이번 주 안내에 정보가 없습니다(UNSET).')
        elif status == 'provided' and (
            record.get('value') is None or
            isinstance(record.get('value'), str) and not record['value'].strip() or
            isinstance(record.get('value'), list) and not record['value']
        ):
            errors.append(f'{name}: 제공 상태인데 실제 값이 비어 있습니다.')
        elif status == 'asset_required' and name not in {
            'opening_song_1', 'opening_song_2', 'opening_song_3',
            'additional_song', 'separate_hymn', 'offering_hymn',
            'special_song', 'decision_hymn', 'song_after_prayer',
            'response_song', 'intercession_song',
        }:
            errors.append(f'{name}: 자료 슬롯만으로 확정할 수 없는 항목입니다.')
        elif state == 'NONE' and name in {'scripture', 'sermon_title'}:
            errors.append(f'{name}: 필수 항목이 없음(NONE)으로 지정되었습니다.')
    return result, errors


def readiness(workspace: Path, service: str, date: str) -> dict:
    d = date.replace('-', '')
    def exists(relative):
        return (workspace / relative).is_file()
    required = []
    if service == 'bulletin':
        required = [
            ('이번 주 전달 주보', f'input/bulletin/{d}/transfer'),
            ('같은 주 주일 안내 해석', f'output/sunday_intake/sunday_{d}_intake.yaml'),
            ('같은 주 주일 기본 데이터', f'output/sunday_intake/sunday-{d}-base.yaml'),
            ('같은 주 주일 통합 데이터', f'output/sunday_intake/sunday-{d}.yaml'),
            ('명시적으로 확인된 주보 호수', f'input/bulletin/{d}/state.yaml'),
        ]
    else:
        root = 'friday_zoom' if service == 'friday' else service
        required = [
            ('이번 주 예배 안내 원문', f'input/{root}/{d}/notices/initial.txt'),
            ('안내 해석·검토 완료 데이터', f'output/{root}_intake/{root}_{d}_intake.yaml'),
        ]
        if service in ('sunday', 'wednesday'):
            required.append(('예배 전 안내 원본', f'input/{service}/{d}/source_rehearsal.pptx'))
            required.append(('명시 등록한 개역개정 본문 데이터', 'data/private/bible_fixed.json'))
        if service == 'friday':
            required.extend([
                ('금요 주간 데이터', f'output/friday_zoom_intake/friday-zoom-{d}.yaml'),
                ('금요 검증 성경 본문', f'output/friday_zoom_intake/friday-zoom-{d}-bible.yaml'),
                ('금요 미디어 체크리스트', f'output/friday_zoom_intake/friday_zoom_{d}_media_checklist.yaml'),
            ])
            for slot in sorted(VIDEO_SLOTS):
                required.append((f'{slot} 영상', f'input/friday_zoom/{d}/{slot}.mp4'))
            for slot in ('first_prayer','word_prayer','community_prayer','personal_prayer'):
                required.append((f'{slot} 음원 (공통 음원 검토는 다음 단계)', f'input/friday_zoom/{d}/{slot}.mp3'))
    present = []
    missing = []
    for label, path in required:
        present_here = any((workspace / 'input/bulletin' / d).glob('transfer.*')) if path.endswith('/transfer') else exists(path)
        (present if present_here else missing).append(label)
    checks = []
    fields = []
    if service != 'bulletin':
        intake = workspace / f'output/{root}_intake/{root}_{d}_intake.yaml'
        if intake.is_file():
            fields, errors = inspect_intake(intake, date, service)
            checks.extend(errors)
            # A correction posted after the parsed intake must not be silently ignored.
            notice_dir = workspace / 'input' / root / d / 'notices'
            newer = [p for p in notice_dir.glob('revision_*.txt')
                     if p.stat().st_mtime_ns >= intake.stat().st_mtime_ns]
            if newer:
                checks.append('추가·수정 안내가 기존 해석 YAML보다 최신입니다. 수정사항을 반영한 새 작업을 준비해주세요.')
            # Files created through the web review retain their input hashes.
            # Verify the full instruction chain, not only filesystem mtimes.
            parsed = _read_yaml(intake) or {}
            web_review = parsed.get('web_review', {})
            confirmed = web_review.get('confirmed_sources') if isinstance(web_review, dict) else None
            if isinstance(confirmed, list):
                known = {entry['path']: entry['sha256'] for entry in confirmed
                         if isinstance(entry, dict) and isinstance(entry.get('path'), str)
                         and isinstance(entry.get('sha256'), str)}
                current = [p.relative_to(workspace).as_posix() for p in notice_dir.glob('*.txt')
                           if p.name == 'initial.txt' or re.fullmatch(r'revision_\d{3}\.txt', p.name)]
                if set(current) != set(known):
                    checks.append('안내 확정 이후 원본 또는 수정 지시 구성이 변경되었습니다. 새 작업에서 다시 확인해주세요.')
                elif any(hashlib.sha256((workspace / path).read_bytes()).hexdigest() != digest
                         for path, digest in known.items()):
                    checks.append('확정 시점과 안내 파일 내용이 다릅니다. 새 작업에서 다시 확인해주세요.')
    else:
        state = workspace / f'input/bulletin/{d}/state.yaml'
        if state.is_file():
            data = _read_yaml(state)
            number = data.get('bulletin_number') if data else None
            if not isinstance(number, str) or not re.fullmatch(r'\d+-\d+', number):
                checks.append('주보 호수를 13-40 같은 형식으로 명시적으로 확인해주세요.')
        # Same-week Sunday intake is shared by the PPT and bulletin. A mismatched
        # or unresolved source must not be silently treated as valid for printing.
        from .common_sunday import summary as sunday_common_summary
        checks.extend(sunday_common_summary(workspace, date)['checks'])
        weekly = workspace / f'output/sunday_intake/sunday-{d}.yaml'
        if weekly.is_file():
            data = _read_yaml(weekly)
            if data is None or str(data.get('date')) != date:
                checks.append('같은 주 주일 통합 데이터의 날짜가 맞지 않습니다.')
    return {'ready': not missing and not checks, 'present': present, 'missing': missing,
            'checks': checks, 'fields': fields, 'note': '파일 존재와 입력 상태만 사전 점검합니다. 본문 정확성·교차검수·악보 확인·인쇄·재생은 별도 검수입니다.'}
