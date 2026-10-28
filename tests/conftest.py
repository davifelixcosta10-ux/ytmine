"""Shared fixtures: builders for the domain objects every test needs."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest

from ytmine.config import DownloadOptions
from ytmine.models import (
    ChannelId,
    License,
    OwnedChannel,
    PrivacyStatus,
    Video,
    VideoId,
)

VIDEO_ID = "dQw4w9WgXcQ"


class VideoFactory(Protocol):
    """Builds a video for a given id, licence and channel."""

    def __call__(self, video_id: str, license_: License, channel_id: str) -> Video:
        """Return a video carrying exactly those three facts."""
        ...


@pytest.fixture
def cc_video() -> Video:
    return Video(
        id=VideoId(VIDEO_ID),
        title="Creative Commons clip",
        channel_id=ChannelId("UCother"),
        channel_title="someone else",
        license=License.CREATIVE_COMMONS,
        privacy=PrivacyStatus.PUBLIC,
    )


@pytest.fixture
def standard_video() -> Video:
    return Video(
        id=VideoId(VIDEO_ID),
        title="Standard licensed clip",
        channel_id=ChannelId("UCother"),
        channel_title="someone else",
        license=License.YOUTUBE,
        privacy=PrivacyStatus.PUBLIC,
    )


@pytest.fixture
def my_video() -> Video:
    return Video(
        id=VideoId(VIDEO_ID),
        title="My own upload",
        channel_id=ChannelId("UCmine"),
        channel_title="my channel",
        license=License.YOUTUBE,
        privacy=PrivacyStatus.PRIVATE,
    )


@pytest.fixture
def my_channel() -> OwnedChannel:
    return OwnedChannel(
        id=ChannelId("UCmine"), title="my channel", uploads_playlist="UUmine"
    )


@pytest.fixture
def options(tmp_path: Path) -> DownloadOptions:
    return DownloadOptions(out_dir=tmp_path / "out")


@pytest.fixture
def make_video() -> VideoFactory:
    """A factory so each test can build videos with distinct ids."""
    return _build_video


def _build_video(video_id: str, license_: License, channel_id: str) -> Video:
    return Video(
        id=VideoId(video_id),
        title=f"title of {video_id}",
        channel_id=ChannelId(channel_id),
        channel_title="a channel",
        license=license_,
        privacy=PrivacyStatus.PUBLIC,
    )
