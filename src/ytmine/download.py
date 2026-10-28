"""Orchestration: gate one video, or a whole channel of them, then download.

The API and the backend are injected as Protocols rather than concrete classes,
so the whole decision path — gate, dry-run, skip, failure — is testable without
a network round trip and without spawning yt-dlp.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol, assert_never

import anyio

from ytmine.backend import Failed, Fetched, FetchRequest, FetchResult, Skipped, fetch
from ytmine.config import DownloadOptions
from ytmine.gate import Allowed, Refused, RightsBasis, judge
from ytmine.models import OwnedChannel, Video, VideoId

_SEQUENTIAL: Final = 1


class VideoLookup(Protocol):
    """The slice of the YouTube API a download job consumes."""

    async def video(self, video_id: VideoId) -> Video:
        """Return the licence and ownership facts for one video."""
        ...


class ChannelReader(Protocol):
    """The slice of the YouTube API a channel listing consumes."""

    async def owned_channel(self) -> OwnedChannel:
        """Return the authenticated account's own channel."""
        ...

    async def upload_video_ids(self, playlist_id: str, limit: int) -> list[VideoId]:
        """Return up to ``limit`` video ids from the uploads playlist."""
        ...


class MediaFetcher(Protocol):
    """Fetches the bytes for one already-gated video."""

    async def __call__(self, request: FetchRequest) -> FetchResult:
        """Run the backend for one request and report the result."""
        ...


@dataclass(frozen=True, slots=True)
class Planned:
    """A ``--dry-run`` verdict: allowed, but nothing was written."""

    video: Video
    basis: RightsBasis


@dataclass(frozen=True, slots=True)
class Saved:
    """Files the backend produced for an allowed video."""

    video: Video
    basis: RightsBasis
    paths: tuple[Path, ...]


@dataclass(frozen=True, slots=True)
class Unchanged:
    """Already in the download archive, so nothing was fetched."""

    video: Video


@dataclass(frozen=True, slots=True)
class Broken:
    """The backend reported a hard failure."""

    video: Video
    status: int


type DownloadOutcome = Planned | Saved | Unchanged | Broken | Refused


@dataclass(frozen=True, slots=True)
class DownloadJob:
    """The shared inputs for one or many downloads."""

    api: VideoLookup
    owned: OwnedChannel | None
    options: DownloadOptions
    dry_run: bool = False
    backend: MediaFetcher = fetch

    async def one(self, video_id: VideoId) -> DownloadOutcome:
        """Gate one video, then download it if the licence policy allows."""
        video = await self.api.video(video_id)
        verdict = judge(video, self.owned)
        match verdict:
            case Allowed(video=video, basis=basis):
                return await self._fetch(video, basis)
            case Refused():
                return verdict
            case unreachable:
                assert_never(unreachable)

    async def many(
        self, video_ids: Sequence[VideoId], parallel: int
    ) -> list[DownloadOutcome]:
        """Download a batch, at most ``parallel`` at a time, order preserved."""
        if parallel <= _SEQUENTIAL or len(video_ids) <= 1:
            return [await self.one(video_id) for video_id in video_ids]
        outcomes: dict[VideoId, DownloadOutcome] = {}
        limiter = anyio.CapacityLimiter(parallel)
        async with anyio.create_task_group() as task_group:
            for video_id in video_ids:
                _ = task_group.start_soon(self._guarded, video_id, limiter, outcomes)
        return [outcomes[video_id] for video_id in video_ids]

    async def _guarded(
        self,
        video_id: VideoId,
        limiter: anyio.CapacityLimiter,
        outcomes: dict[VideoId, DownloadOutcome],
    ) -> None:
        """Run one download under the concurrency limiter and record it."""
        async with limiter:
            outcomes[video_id] = await self.one(video_id)

    async def _fetch(self, video: Video, basis: RightsBasis) -> DownloadOutcome:
        """Download an already-gated video, or report what would have happened."""
        if self.dry_run:
            return Planned(video=video, basis=basis)
        result = await self.backend(
            FetchRequest(video_id=video.id, options=self.options)
        )
        match result:
            case Fetched(paths=paths):
                return Saved(video=video, basis=basis, paths=paths)
            case Skipped():
                return Unchanged(video=video)
            case Failed(status=status):
                return Broken(video=video, status=status)
            case unreachable:
                assert_never(unreachable)


@dataclass(frozen=True, slots=True)
class ChannelBatch:
    """The user's own uploads, ready to be downloaded."""

    channel: OwnedChannel
    video_ids: tuple[VideoId, ...]


async def read_channel_batch(api: ChannelReader, limit: int) -> ChannelBatch:
    """Read the authenticated channel's own uploads playlist."""
    channel = await api.owned_channel()
    video_ids = await api.upload_video_ids(channel.uploads_playlist, limit)
    return ChannelBatch(channel=channel, video_ids=tuple(video_ids))
