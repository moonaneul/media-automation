"""Read-only audit of hosted song catalog vs typed worship runtime resources.

Does not download OneDrive objects, edit catalog records, or make network calls.
An item being present here says nothing about copyright, review or playback.
"""
from collections import Counter
from pathlib import PurePosixPath

from ..web.original.original_roles import original_role, song_candidate


def runtime_category(path):
    """Classify trusted *runtime inventory paths*, not arbitrary song filenames."""
    value = str(path).replace('\\', '/')
    if value.startswith('assets/private/bulletin/'):
        return 'bulletin'
    if value.startswith('assets/private/friday_reference/'):
        return 'friday_template'
    if value.startswith('assets/private/friday_zoom/'):
        return 'friday_music'
    if value.startswith('assets/worship/'):
        return 'worship_template'
    if value.startswith('data/private/bible'):
        return 'scripture'
    return 'other_runtime'


def inspect_catalog(snapshot):
    """Return safe metadata to an already authenticated media-team caller."""
    tables = snapshot.get('tables', {})
    songs = tables.get('songs', [])
    assets = tables.get('song_assets', [])
    by_id = {r['id']: r.get('payload', {}) for r in songs}
    suspicious = []
    seen = set()
    for item in assets:
        role = original_role(item.get('filename', ''))
        if song_candidate(item.get('filename', '')):
            continue
        song = by_id.get(item.get('song_id'), {})
        suspicious.append({
            'song_id': item.get('song_id', ''),
            'title': song.get('title', ''),
            'filename': item.get('filename', ''),
            'suggested_role': role,
        })
        seen.add(item.get('song_id'))
    for item in songs:
        title = item.get('payload', {}).get('title', '')
        assumed = original_role(title + '.pptx')
        if item['id'] not in seen and assumed not in ('score', 'song_video', 'audio_candidate'):
            suspicious.append({
                'song_id': item['id'],
                'title': title,
                'filename': '',
                'suggested_role': assumed,
            })
    kinds = Counter(runtime_category(r.get('path', '')) for r in tables.get('runtime_assets', []))
    return {
        'read_only': True,
        'song_count': len(songs),
        'song_asset_count': len(assets),
        'misclassified_count': len(suspicious),
        'misclassified': suspicious,
        'runtime_resource_count': sum(kinds.values()),
        'runtime_types': dict(sorted(kinds.items())),
        'note': '곡명·확장자에 기반한 검토 대상입니다. 파일 내용, 실제 재생, 사용 허락은 별도로 검증해야 합니다.',
    }
