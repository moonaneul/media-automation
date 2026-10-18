"""Hosted media catalog review is read-only and does not touch OneDrive."""
from media_automation.cloud.catalog_audit import inspect_catalog


def test_hosted_catalog_audit_identifies_non_songs_and_runtime_assets():
    snapshot = {
        'tables': {
            'songs': [
                {'id': 'hymn', 'payload': {'title': '주 하나님 지으신 모든 세계'}},
                {'id': 'cover', 'payload': {'title': 'cover'}},
                {'id': 'music', 'payload': {'title': '금요 공동체·개인 기도 배경음원'}},
            ],
            'song_assets': [
                {'song_id': 'hymn', 'filename': '찬송가 79장.pptx', 'digest': 'a' * 64},
                {'song_id': 'cover', 'filename': 'cover_' + 'b' * 64 + '.pptx', 'digest': 'b' * 64},
                {'song_id': 'music', 'filename': '금요 공동체·개인 기도 배경음원.mp3', 'digest': 'c' * 64},
            ],
            'runtime_assets': [
                {'path': 'assets/private/bulletin/original-design.pdf'},
                {'path': 'assets/private/friday_reference/community-prayer.pptx'},
                {'path': 'assets/private/friday_zoom/music.json'},
                {'path': 'assets/worship/wednesday-start.pptx'},
                {'path': 'data/private/bible_fixed.json'},
            ],
        },
    }
    result = inspect_catalog(snapshot)
    assert result['read_only'] is True
    assert result['song_count'] == 3
    assert result['song_asset_count'] == 3
    assert result['misclassified_count'] == 2
    assert {(r['title'], r['suggested_role']) for r in result['misclassified']} == {
        ('cover', 'bulletin'),
        ('금요 공동체·개인 기도 배경음원', 'prayer_audio'),
    }
    assert result['runtime_types'] == {
        'bulletin': 1, 'friday_music': 1, 'friday_template': 1,
        'scripture': 1, 'worship_template': 1,
    }
    assert result['runtime_resource_count'] == 5
    assert 'digest' not in str(result)


def test_title_only_misclassification_stays_visible_for_manual_review():
    result = inspect_catalog({'tables': {
        'songs': [{'id': 'x', 'payload': {'title': 'bulletin-runtime-original-design'}}],
        'song_assets': [],
        'runtime_assets': [],
    }})
    assert result['misclassified_count'] == 1
    assert result['misclassified'][0]['filename'] == ''
