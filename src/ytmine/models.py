"""Domain types plus the typed boundary for YouTube Data API v3 payloads.

The two identifiers YouTube hands back are branded with ``NewType`` so a channel
id can never be passed where a video id is expected. Everything below the API
boundary is a frozen dataclass; everything crossing it is a Pydantic model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, NewType

from pydantic import BaseModel, ConfigDict

VideoId = NewType("VideoId", str)
ChannelId = NewType("ChannelId", str)


@unique
class License(StrEnum):
    """The two licences YouTube reports for a video."""

    YOUTUBE = "youtube"
    CREATIVE_COMMONS = "creativeCommon"


@unique
class PrivacyStatus(StrEnum):
    """Visibility of a video as reported by the API."""

    PUBLIC = "public"
    UNLISTED = "unlisted"
    PRIVATE = "private"


@dataclass(frozen=True, slots=True)
class Video:
    """A video whose licence and ownership the API has resolved."""

    id: VideoId
    title: str
    channel_id: ChannelId
    channel_title: str
    license: License
    privacy: PrivacyStatus

    @property
    def url(self) -> str:
        """Canonical watch URL for this video."""
        return f"https://www.youtube.com/watch?v={self.id}"


@dataclass(frozen=True, slots=True)
class OwnedChannel:
    """The authenticated user's own channel and its uploads playlist."""

    id: ChannelId
    title: str
    uploads_playlist: str


@dataclass(frozen=True, slots=True)
class UploadRef:
    """One video id found in the user's uploads playlist."""

    video_id: VideoId
    title: str


# ── Boundary models: YouTube Data API v3 ──


class _Resource(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)


class VideoStatusPayload(_Resource):
    license: str = ""
    privacyStatus: str = ""


class VideoSnippetPayload(_Resource):
    title: str = ""
    channelId: str = ""
    channelTitle: str = ""
    publishedAt: str = ""


class VideoResource(_Resource):
    id: str
    snippet: VideoSnippetPayload
    status: VideoStatusPayload


class VideoListResponse(_Resource):
    items: list[VideoResource] = []


class RelatedPlaylistsPayload(_Resource):
    uploads: str = ""


class ChannelContentDetailsPayload(_Resource):
    relatedPlaylists: RelatedPlaylistsPayload = RelatedPlaylistsPayload()


class ChannelSnippetPayload(_Resource):
    title: str = ""


class ChannelResource(_Resource):
    id: str
    snippet: ChannelSnippetPayload
    contentDetails: ChannelContentDetailsPayload


class ChannelListResponse(_Resource):
    items: list[ChannelResource] = []


class PlaylistItemSnippetPayload(_Resource):
    title: str = ""
    publishedAt: str = ""


class PlaylistItemContentDetailsPayload(_Resource):
    videoId: str = ""


class PlaylistItemResource(_Resource):
    snippet: PlaylistItemSnippetPayload
    contentDetails: PlaylistItemContentDetailsPayload


class PlaylistItemListResponse(_Resource):
    items: list[PlaylistItemResource] = []
    nextPageToken: str | None = None
