"""Orchestration: the gate decides, the backend only ever sees what passed."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Final, override

import anyio
import pytest

from ytmine.backend import Failed, Fetched, FetchRequest, FetchResult, Skipped
from ytmine.config import DownloadOptions
from ytmine.download import (
    Broken,
    ChannelBatch,
    ChannelReader,
    DownloadJob,
    MediaFetcher,
    Planned,
    Saved,
    Unchanged,
    VideoLookup,
    read_channel_batch,
)
from ytmine.gate import Refused
from ytmine.models import (
    License,
    OwnedChannel,
    Video,
    VideoId,
)

_CC: Final = VideoId("dQw4w9WgXcQ")
_MINE: Final = VideoId("abcdefghijk")
_STANDARD: Final = VideoId("lmnopqrstuv")
_PATH: Final = Path("out/creative-clip.mp4")


class _FakeLookup(VideoLookup):
    """In-memory stand-in for the API surface a job consumes.

    Mutation is its purpose: it records what the job asked for.
    """

    def __init__(self, videos: dict[VideoId, Video]) -> None:
        self.videos: dict[VideoId, Video] = videos
        self.seen: list[VideoId] = []

    @override
    async def video(self, video_id: VideoId) -> Video:
        self.seen.append(video_id)
        return self.videos[video_id]


class _FakeChannelReader(ChannelReader):
    """In-memory stand-in for listing the user's own uploads."""

    def __init__(self, channel: OwnedChannel, ids: list[VideoId]) -> None:
        self._channel: OwnedChannel = channel
        self._ids: list[VideoId] = ids

    @override
    async def owned_channel(self) -> OwnedChannel:
        return self._channel

    @override
    async def upload_video_ids(self, playlist_id: str, limit: int) -> list[VideoId]:
        return self._ids[:limit]


def _stub_backend(result: FetchResult) -> tuple[MediaFetcher, list[FetchRequest]]:
    """A backend that records its requests and always returns ``result``."""
    seen: list[FetchRequest] = []

    async def backend(request: FetchRequest) -> FetchResult:
        seen.append(request)
        return result

    return backend, seen


def _job(
    api: VideoLookup,
    owned: OwnedChannel | None,
    options: DownloadOptions,
    backend: MediaFetcher,
    dry_run: bool = False,
) -> DownloadJob:
    return DownloadJob(
        api=api, owned=owned, options=options, dry_run=dry_run, backend=backend
    )


class Test_DownloadJob_one:
    """Given one video id, when the job runs it, then the gate decides."""

    def test_downloads_a_creative_commons_video(
        self, cc_video: Video, options: DownloadOptions
    ) -> None:
        backend, seen = _stub_backend(Fetched(video_id=_CC, paths=(_PATH,)))
        job = _job(_FakeLookup({_CC: cc_video}), None, options, backend)

        outcome = anyio.run(job.one, _CC)

        assert isinstance(outcome, Saved)
        assert outcome.video is cc_video
        assert outcome.paths == (_PATH,)
        assert len(seen) == 1

    def test_downloads_a_video_from_the_owned_channel(
        self, my_video: Video, my_channel: OwnedChannel, options: DownloadOptions
    ) -> None:
        backend, seen = _stub_backend(Fetched(video_id=_MINE, paths=()))
        job = _job(_FakeLookup({_MINE: my_video}), my_channel, options, backend)

        outcome = anyio.run(job.one, _MINE)

        assert isinstance(outcome, Saved)
        assert outcome.video is my_video
        assert len(seen) == 1

    def test_never_reaches_the_backend_for_a_strangers_video(
        self, standard_video: Video, my_channel: OwnedChannel, options: DownloadOptions
    ) -> None:
        backend, seen = _stub_backend(Fetched(video_id=_STANDARD, paths=()))
        job = _job(
            _FakeLookup({_STANDARD: standard_video}), my_channel, options, backend
        )

        outcome = anyio.run(job.one, _STANDARD)

        assert isinstance(outcome, Refused)
        assert seen == []

    def test_reports_a_skip_when_the_archive_already_has_it(
        self, cc_video: Video, options: DownloadOptions
    ) -> None:
        backend, _ = _stub_backend(Skipped(video_id=_CC))
        job = _job(_FakeLookup({_CC: cc_video}), None, options, backend)

        outcome = anyio.run(job.one, _CC)

        assert isinstance(outcome, Unchanged)
        assert outcome.video is cc_video

    def test_reports_a_failure_when_the_backend_fails(
        self, cc_video: Video, options: DownloadOptions
    ) -> None:
        backend, _ = _stub_backend(Failed(video_id=_CC, status=1))
        job = _job(_FakeLookup({_CC: cc_video}), None, options, backend)

        outcome = anyio.run(job.one, _CC)

        assert isinstance(outcome, Broken)
        assert outcome.status == 1

    def test_dry_run_stops_before_the_backend(
        self, cc_video: Video, options: DownloadOptions
    ) -> None:
        backend, seen = _stub_backend(Fetched(video_id=_CC, paths=()))
        job = _job(_FakeLookup({_CC: cc_video}), None, options, backend, dry_run=True)

        outcome = anyio.run(job.one, _CC)

        assert isinstance(outcome, Planned)
        assert seen == []


class Test_DownloadJob_many:
    """Given several ids, when the batch runs, then order and gating hold."""

    @pytest.mark.parametrize("parallel", [1, 3])
    def test_keeps_the_order_and_the_verdicts_of_the_input(
        self,
        make_video: Callable[[str, License, str], Video],
        options: DownloadOptions,
        parallel: int,
    ) -> None:
        videos = {
            _CC: make_video(_CC, License.CREATIVE_COMMONS, "UCother"),
            _STANDARD: make_video(_STANDARD, License.YOUTUBE, "UCother"),
            _MINE: make_video(_MINE, License.YOUTUBE, "UCmine"),
        }
        backend, _ = _stub_backend(Fetched(video_id=_CC, paths=()))
        job = _job(_FakeLookup(videos), None, options, backend)

        outcomes = anyio.run(job.many, [_CC, _STANDARD, _MINE], parallel)

        assert [type(outcome) for outcome in outcomes] == [Saved, Refused, Refused]
        assert [outcome.video.id for outcome in outcomes] == [_CC, _STANDARD, _MINE]


class Test_read_channel_batch:
    """Given a channel reader, when the batch is read, then ids come back."""

    def test_returns_the_channels_own_uploads(self, my_channel: OwnedChannel) -> None:
        reader = _FakeChannelReader(my_channel, [_CC, _MINE, _STANDARD])

        batch = anyio.run(read_channel_batch, reader, 2)

        assert isinstance(batch, ChannelBatch)
        assert batch.channel is my_channel
        assert batch.video_ids == (_CC, _MINE)
