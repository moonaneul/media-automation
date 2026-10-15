"""Cloud Run source lookup and uploads classify song files before writes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from media_automation.cloud.http import Hosted


@pytest.mark.parametrize("filename", [
    "cover.pptx",
    "bulletin-runtime-original-design.pdf",
    "community-prayer_2ccc7267af27b1405a1b7a16f57987e1fe8a5666ca802818bc2c4ee5f35f35ce.pptx",
    "금요 공동체·개인 기도 배경음원.mp3",
])
def test_direct_cloud_song_upload_rejects_non_song_before_storage(filename):
    hosted = object.__new__(Hosted)
    hosted.cloud = Mock()
    with pytest.raises(ValueError, match="찬양이 아닌"):
        hosted.upload(None, "/api/song-assets",
                      {"filename": [filename], "song_id": ["song-1"]}, b"test")
    hosted.cloud.selected.assert_not_called()


@pytest.mark.parametrize("filename", ["cover.pptx", "community-prayer.mp3", "bulletin-runtime-original-design.pdf"])
def test_chunked_cloud_song_upload_rejects_non_song_before_upload_session(filename):
    hosted = object.__new__(Hosted)
    hosted.cloud = Mock()
    body = {
        "filename": filename, "size": 4, "digest": "f" * 64,
        "route": "/api/song-assets", "query": {"song_id": "song-1"},
    }
    with pytest.raises(ValueError, match="찬양이 아닌"):
        hosted.upload_start(None, SimpleNamespace(user_id="user"), body)
    hosted.cloud.graph.assert_not_called()


def test_cloud_source_search_requires_song_query_before_listing():
    hosted = object.__new__(Hosted)
    hosted.cloud = Mock()
    handler = SimpleNamespace(command="GET", reply=lambda code, body: (code, body))
    parsed = SimpleNamespace(path="/api/onedrive/files", query="purpose=source")
    with pytest.raises(ValueError, match="곡명"):
        hosted.onedrive(handler, None, parsed)
    hosted.cloud.list_selected.assert_not_called()


def test_cloud_source_search_tags_non_song_roles_read_only():
    hosted = object.__new__(Hosted)
    cloud = Mock()
    cloud.list_selected.return_value = [
        {"id": "a", "name": "cover.pptx", "file": {}},
        {"id": "b", "name": "찬양 제목.pptx", "file": {}},
        {"id": "c", "name": "금요 공동체·개인 기도 배경음원.mp3", "file": {}},
    ]
    hosted.cloud = cloud
    handler = SimpleNamespace(command="GET", reply=lambda code, body: (code, body))
    parsed = SimpleNamespace(path="/api/onedrive/files", query="purpose=source&q=%EC%B0%AC%EC%96%91")
    status, response = hosted.onedrive(handler, None, parsed)
    assert status == 200
    assert [row["source_role"] for row in response["items"]] == [
        "bulletin", "score", "prayer_audio",
    ]
    cloud.list_selected.assert_called_once_with("source", None, "찬양")
