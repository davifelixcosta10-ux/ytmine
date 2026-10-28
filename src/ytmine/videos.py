"""Parse a YouTube reference into a ``VideoId``. This is the only front door."""

from __future__ import annotations

import re
from typing import Final
from urllib.parse import parse_qs, urlparse

from ytmine.errors import NotYouTubeUrlError
from ytmine.models import VideoId

_BARE_ID: Final = re.compile(r"^[A-Za-z0-9_-]{11}$")

_HOSTS: Final = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "music.youtube.com",
        "youtube-nocookie.com",
        "www.youtube-nocookie.com",
    }
)

_SHORT_HOST: Final = "youtu.be"

_SEGMENT_PREFIXES: Final = frozenset({"shorts", "live", "embed"})


def parse_video_ref(raw: str) -> VideoId:
    """Turn a watch/shorts/live/embed URL, a youtu.be link, or a bare id into an id.

    Raises:
        NotYouTubeUrlError: the reference is not on YouTube at all.
    """
    text = raw.strip()
    if _BARE_ID.fullmatch(text):
        return VideoId(text)

    parsed = urlparse(text)
    if parsed.scheme != "https":
        raise NotYouTubeUrlError(url=raw)

    host = parsed.hostname or ""
    if host == _SHORT_HOST:
        candidate = parsed.path.lstrip("/").split("/")[0]
    elif host in _HOSTS:
        candidate = _from_watch_url(parsed.path, parsed.query)
    else:
        raise NotYouTubeUrlError(url=raw)

    if not _BARE_ID.fullmatch(candidate):
        raise NotYouTubeUrlError(url=raw)
    return VideoId(candidate)


def _from_watch_url(path: str, query: str) -> str:
    """Extract the id from a youtube.com path plus its query string."""
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return ""
    head, *rest = segments
    if head == "watch":
        values = parse_qs(query).get("v", [])
        return values[0] if values else ""
    if head in _SEGMENT_PREFIXES and rest:
        return rest[0]
    return ""
