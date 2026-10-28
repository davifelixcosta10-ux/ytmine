"""Typed errors. Every failure carries structured data and a real ``__str__``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import override

from ytmine.models import VideoId


class YtmineError(Exception):
    """Base class for every error ytmine raises."""


@dataclass(frozen=True, slots=True)
class NotYouTubeUrlError(YtmineError):
    """A URL that does not point at youtube.com or youtu.be."""

    url: str

    @override
    def __str__(self) -> str:
        return f"not a YouTube URL: {self.url!r}"


@dataclass(frozen=True, slots=True)
class VideoNotFoundError(YtmineError):
    """The API returned no resource: deleted, private, or unknown id."""

    video_id: VideoId

    @override
    def __str__(self) -> str:
        return f"video {self.video_id} not found, private, or deleted"


@dataclass(frozen=True, slots=True)
class TokenMissingError(YtmineError):
    """No cached OAuth token and no way to run the interactive flow."""

    @override
    def __str__(self) -> str:
        return "not authorised yet — run `ytmine auth` first"


@dataclass(frozen=True, slots=True)
class YouTubeApiError(YtmineError):
    """A non-quota YouTube Data API failure."""

    status: int
    reason: str

    @override
    def __str__(self) -> str:
        return f"YouTube Data API error {self.status}: {self.reason}"


@dataclass(frozen=True, slots=True)
class AccountHasNoChannelError(YtmineError):
    """The authorised account owns no YouTube channel."""

    @override
    def __str__(self) -> str:
        return "the authorised account has no YouTube channel"


@dataclass(frozen=True, slots=True)
class QuotaExceededError(YtmineError):
    """The daily YouTube Data API quota is exhausted."""

    reason: str

    @override
    def __str__(self) -> str:
        return f"YouTube Data API quota exceeded: {self.reason}"


@dataclass(frozen=True, slots=True)
class AuthorizationError(YtmineError):
    """The OAuth round trip could not be completed."""

    reason: str

    @override
    def __str__(self) -> str:
        return f"authorisation failed: {self.reason}"


@dataclass(frozen=True, slots=True)
class ClientSecretsMissingError(YtmineError):
    """No Google OAuth client-secrets file where the config says it is."""

    path: str

    @override
    def __str__(self) -> str:
        return (
            f"OAuth client secrets not found at {self.path}. In Google Cloud "
            "Console: enable YouTube Data API v3, create an OAuth client of "
            "type 'Desktop app', download the JSON and save it there."
        )


@dataclass(frozen=True, slots=True)
class BackendUnavailableError(YtmineError):
    """The yt-dlp binary is not on PATH."""

    command: str

    @override
    def __str__(self) -> str:
        return f"backend {self.command!r} not found on PATH — install yt-dlp"


@dataclass(frozen=True, slots=True)
class BackendFailedError(YtmineError):
    """yt-dlp exited with a status that is neither success nor skip."""

    command: str
    status: int
    video_id: VideoId

    @override
    def __str__(self) -> str:
        return f"{self.command} failed on {self.video_id} with status {self.status}"
