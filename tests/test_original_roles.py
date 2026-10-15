"""Regression checks: non-song originals never become song candidates."""
from media_automation.web.original.original_roles import (
    can_auto_register_hymn, original_role, song_candidate,
)
from media_automation.web.original.onedrive import OneDrive


def test_non_song_runtime_assets_are_classified_separately():
    cases = {
        "bulletin-runtime-original-design.pdf": "bulletin",
        "cover.png": "image",
        "cover.pptx": "bulletin",
        "community-prayer.mp3": "prayer_audio",
        "worship-template.pptx": "worship_template",
        "original-bold.ttf": "bulletin_font",
        "2026-10-07-wednesday-abc123.pptx": "completed_output",
    }
    for name, kind in cases.items():
        assert original_role(name) == kind
        assert not song_candidate(name)


def test_church_song_assets_remain_candidates():
    assert original_role("382장_너 근심 걱정 말아라.ppt") == "score"
    assert original_role("주가 일하시네.mp4") == "song_video"
    assert original_role("기도.mp3") == "audio_candidate"
    assert song_candidate("382장_너 근심 걱정 말아라.ppt")


def test_automatic_creation_requires_explicit_named_hymnal_score():
    confirmed = OneDrive.filename_metadata("193장_성령의 봄바람 불어오니_새찬송가악보_PPT.ppt")
    assert can_auto_register_hymn(confirmed, "193장_성령의 봄바람 불어오니_새찬송가악보_PPT.ppt")
    for filename in ("cover.pptx", "bulletin-runtime-original-design.pdf", "community-prayer.mp3", "교회여 일어나라.mp4"):
        assert not can_auto_register_hymn(OneDrive.filename_metadata(filename), filename)
