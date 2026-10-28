"""Boundary tests: parse_video_ref turns a YouTube reference into a VideoId."""

from __future__ import annotations

import pytest

from ytmine.errors import NotYouTubeUrlError
from ytmine.models import VideoId
from ytmine.videos import parse_video_ref

VIDEO_ID = "dQw4w9WgXcQ"

WATCH_FORMS = [
    f"https://www.youtube.com/watch?v={VIDEO_ID}",
    f"https://youtube.com/watch?v={VIDEO_ID}",
    f"https://m.youtube.com/watch?v={VIDEO_ID}",
    f"https://music.youtube.com/watch?v={VIDEO_ID}",
    f"https://www.youtube.com/watch?app=desktop&v={VIDEO_ID}",
    f"https://youtu.be/{VIDEO_ID}",
    f"https://youtu.be/{VIDEO_ID}?t=42",
    f"https://www.youtube.com/shorts/{VIDEO_ID}",
    f"https://www.youtube.com/live/{VIDEO_ID}",
    f"https://www.youtube.com/embed/{VIDEO_ID}",
    f"https://www.youtube-nocookie.com/embed/{VIDEO_ID}",
    f"   {VIDEO_ID}   ",
]


class Test_parse_video_ref:
    """Given a reference, when it is parsed, then the id comes back."""

    @pytest.mark.parametrize("raw", WATCH_FORMS)
    def test_returns_the_id_for_every_supported_form(self, raw: str) -> None:
        assert parse_video_ref(raw) == VideoId(VIDEO_ID)

    @pytest.mark.parametrize(
        "raw",
        [
            "https://vimeo.com/12345",
            "https://www.dailymotion.com/video/x7abcde",
            "https://pornhub.com/view_video.php?viewkey=abc",
            "https://www.twitch.tv/videos/12345",
            "https://example.com/watch?v=dQw4w9WgXcQ",
            "http://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://www.youtube.com/watch?v=toshort",
            "https://www.youtube.com/watch?v=thisidiswaytoolongforavideoid",
            "https://www.youtube.com/",
            "",
            "   ",
        ],
    )
    def test_refuses_anything_that_is_not_youtube(self, raw: str) -> None:
        with pytest.raises(NotYouTubeUrlError):
            _ = parse_video_ref(raw)
