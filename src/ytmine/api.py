"""Typed wrapper over the YouTube Data API v3.

Every call goes through ``_get``: the token is refreshed lazily, the response
text is parsed straight into a Pydantic model, and any non-2xx status becomes a
typed error. Nothing below this module deals with JSON.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import ClassVar, Final, NoReturn

import httpx2
from pydantic import BaseModel, ConfigDict

from ytmine.errors import (
    AccountHasNoChannelError,
    QuotaExceededError,
    VideoNotFoundError,
    YouTubeApiError,
)
from ytmine.http import create_async_client
from ytmine.models import (
    ChannelId,
    ChannelListResponse,
    ChannelResource,
    License,
    OwnedChannel,
    PlaylistItemListResponse,
    PrivacyStatus,
    UploadRef,
    Video,
    VideoId,
    VideoListResponse,
    VideoResource,
)
from ytmine.token import Credentials, ensure_fresh

_API_ROOT: Final = "https://www.googleapis.com/youtube/v3/"
_VIDEOS: Final = "videos"
_CHANNELS: Final = "channels"
_PLAYLIST_ITEMS: Final = "playlistItems"
_PAGE_SIZE: Final = 50
_OK: Final = 200
_FORBIDDEN: Final = 403

_QUOTA_REASONS: Final = frozenset(
    {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"}
)


# A plain dict of strings: httpx2's own parameter shape is Mapping[str, str | int
# | float], and a TypedDict does not structurally satisfy that.
type ApiParams = dict[str, str]


class _ErrorDetailPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    reason: str = ""
    message: str = ""


class _ErrorEnvelopePayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    error: _ErrorDetailPayload


class YouTubeClient:
    """One authenticated session against the YouTube Data API."""

    def __init__(self, credentials: Credentials, http: httpx2.AsyncClient) -> None:
        self._credentials: Credentials = credentials
        self._http: httpx2.AsyncClient = http

    async def video(self, video_id: VideoId) -> Video:
        """Fetch the licence and ownership facts for one video.

        Raises:
            VideoNotFoundError: the video is deleted, private, or unknown.
        """
        text = await self._get(_VIDEOS, {"part": "snippet,status", "id": video_id})
        response = VideoListResponse.model_validate_json(text)
        resource = response.items[0] if response.items else None
        if resource is None:
            raise VideoNotFoundError(video_id=video_id)
        return to_video(resource)

    async def owned_channel(self) -> OwnedChannel:
        """The authenticated account's own channel and its uploads playlist.

        Raises:
            AccountHasNoChannelError: the authorised account has no channel.
        """
        text = await self._get(
            _CHANNELS, {"part": "snippet,contentDetails", "mine": "true"}
        )
        response = ChannelListResponse.model_validate_json(text)
        resource = response.items[0] if response.items else None
        if resource is None:
            raise AccountHasNoChannelError
        return _to_channel(resource)

    async def owned_channel_or_none(self) -> OwnedChannel | None:
        """The user's own channel, or ``None`` when the account has none."""
        try:
            return await self.owned_channel()
        except AccountHasNoChannelError:
            return None

    async def uploads(
        self, playlist_id: str, page_token: str | None = None
    ) -> tuple[list[UploadRef], str | None]:
        """Fetch one page of an uploads playlist, plus the next page token."""
        params: ApiParams = {
            "part": "snippet,contentDetails",
            "playlistId": playlist_id,
            "maxResults": str(_PAGE_SIZE),
        }
        if page_token is not None:
            params["pageToken"] = page_token
        text = await self._get(_PLAYLIST_ITEMS, params)
        response = PlaylistItemListResponse.model_validate_json(text)
        refs = [
            UploadRef(
                video_id=VideoId(item.contentDetails.videoId), title=item.snippet.title
            )
            for item in response.items
        ]
        return refs, response.nextPageToken

    async def upload_video_ids(self, playlist_id: str, limit: int) -> list[VideoId]:
        """Walk the uploads playlist until it ends or ``limit`` ids are collected."""
        collected: list[VideoId] = []
        token: str | None = None
        while len(collected) < limit:
            refs, token = await self.uploads(playlist_id, token)
            collected.extend(ref.video_id for ref in refs)
            if token is None:
                break
        return collected[:limit]

    async def _get(self, endpoint: str, params: ApiParams) -> str:
        """Issue an authenticated GET against one API endpoint."""
        headers = await self._headers()
        response = await self._http.get(
            f"{_API_ROOT}{endpoint}", params=params, headers=headers
        )
        if response.status_code != _OK:
            raise_api_error(response)
        return response.text

    async def _headers(self) -> dict[str, str]:
        """Refresh the token when needed, then return the bearer header."""
        self._credentials = await ensure_fresh(self._credentials)
        return {"Authorization": f"Bearer {self._credentials.access_token}"}


@asynccontextmanager
async def youtube_api(credentials: Credentials) -> AsyncGenerator[YouTubeClient]:
    """Open an authenticated session and close its HTTP pool on exit."""
    async with create_async_client() as http:
        yield YouTubeClient(credentials, http)


def to_video(resource: VideoResource) -> Video:
    """Map an API video resource onto the domain ``Video``."""
    return Video(
        id=VideoId(resource.id),
        title=resource.snippet.title,
        channel_id=ChannelId(resource.snippet.channelId),
        channel_title=resource.snippet.channelTitle,
        license=to_license(resource.status.license),
        privacy=to_privacy(resource.status.privacyStatus),
    )


def _to_channel(resource: ChannelResource) -> OwnedChannel:
    """Map an API channel resource onto the domain ``OwnedChannel``."""
    return OwnedChannel(
        id=ChannelId(resource.id),
        title=resource.snippet.title,
        uploads_playlist=resource.contentDetails.relatedPlaylists.uploads,
    )


def to_license(raw: str) -> License:
    """Map the API licence string; anything unknown means YouTube's default."""
    for license_ in License:
        if license_.value == raw:
            return license_
    return License.YOUTUBE


def to_privacy(raw: str) -> PrivacyStatus:
    """Map the API privacy string; anything unknown means private."""
    for status in PrivacyStatus:
        if status.value == raw:
            return status
    return PrivacyStatus.PRIVATE


def _error_reason(text: str) -> str:
    """Pull `reason` out of a Google error envelope, or return the raw head."""
    try:
        payload = _ErrorEnvelopePayload.model_validate_json(text)
    except ValueError:
        return text[:200]
    return payload.error.reason or payload.error.message or text[:200]


def raise_api_error(response: httpx2.Response) -> NoReturn:
    """Turn a non-2xx API response into the matching typed error."""
    reason = _error_reason(response.text)
    if _is_quota(response.status_code, reason):
        raise QuotaExceededError(reason=reason)
    raise YouTubeApiError(status=response.status_code, reason=reason)


def _is_quota(status: int, reason: str) -> bool:
    """True when a status and reason together mean the daily quota is gone."""
    forbidden = status == _FORBIDDEN
    return forbidden and any(tag in reason for tag in _QUOTA_REASONS)
