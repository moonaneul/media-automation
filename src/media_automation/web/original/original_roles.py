"""Classify worship source files before treating anything as a song.

The original file is owned by OneDrive (or by the church's private runtime
assets). A filename never proves that the file is a song or that its use was
approved. Unknown sources must wait for explicit review, not become songs.
This module never moves, downloads, or deletes originals.
"""
from pathlib import Path
import re

SCORE_EXTENSIONS = frozenset({'.ppt', '.pptx'})
SONG_VIDEO_EXTENSIONS = frozenset({'.mp4'})
AUDIO_EXTENSIONS = frozenset({'.mp3', '.wav'})
SONG_EXTENSIONS = SCORE_EXTENSIONS | SONG_VIDEO_EXTENSIONS | AUDIO_EXTENSIONS


def original_role(filename):
    """Return the likely *functional* role; non-song files never enter songs."""
    path = Path(filename)
    ext = path.suffix.lower()
    name = re.sub(r'[_-][0-9a-f]{32,64}$', '', path.stem, flags=re.I)
    normalized = re.sub(r'[\s_-]+', '-', name.strip().casefold()).strip('-')

    if ext in {'.ttf', '.otf', '.woff', '.woff2'}:
        return 'bulletin_font'
    if ext in {'.jpg', '.jpeg', '.png', '.webp'}:
        return 'image'
    if (normalized == 'cover' or normalized.startswith(('bulletin-', '주보-', '주보표지', '표지-'))
            or normalized in {'bulletin', '주보'}):
        return 'bulletin'
    if ext == '.pdf':
        return 'document'
    if (normalized.startswith(('community-prayer', 'prayer-background', 'background-music',
                                'friday-prayer', '금요-기도-배경', '금요-공동체'))
            or normalized in {'community-prayer', '기도-배경음악'}):
        return 'prayer_audio' if ext in AUDIO_EXTENSIONS else 'worship_template'
    if (normalized.startswith(('worship-template', 'service-template', '예배-템플릿',
                                '예배-안내-배경', 'friday-reference'))):
        return 'worship_template'
    if re.match(r'^\d{4}-\d{2}-\d{2}-(?:sunday|wednesday|friday)(?:-|$)', normalized):
        return 'completed_output'

    if ext in SCORE_EXTENSIONS:
        return 'score'
    if ext in SONG_VIDEO_EXTENSIONS:
        return 'song_video'
    if ext in AUDIO_EXTENSIONS:
        return 'audio_candidate'
    return 'other'


def song_candidate(filename):
    """Only plausible score/video/audio originals can be linked to a song."""
    return original_role(filename) in {'score', 'song_video', 'audio_candidate'}


def can_auto_register_hymn(metadata, filename):
    """A numbered *named* hymnal is enough to create metadata automatically.

    CCM and Zoom videos may be matched against an existing song, but are not
    registered from arbitrary first words of filenames (e.g. 'cover.pdf').
    """
    return (original_role(filename) == 'score' and isinstance(metadata, dict)
            and metadata.get('edition') in ('new', 'old')
            and type(metadata.get('number')) is int
            and 1 <= metadata['number'] <= 999
            and bool(metadata.get('title', '').strip()))
