"""The rights gate: only Creative Commons and your own uploads are allowed."""

from __future__ import annotations

import pytest

from ytmine.gate import Allowed, Refused, RightsBasis, Verdict, judge
from ytmine.models import (
    ChannelId,
    License,
    OwnedChannel,
    PrivacyStatus,
    Video,
    VideoId,
)

_MINE = ChannelId("UCmine")
_OTHER = ChannelId("UCother")


def _video(license_: License, channel_id: ChannelId = _OTHER) -> Video:
    return Video(
        id=VideoId("dQw4w9WgXcQ"),
        title="a title",
        channel_id=channel_id,
        channel_title="a channel",
        license=license_,
        privacy=PrivacyStatus.PUBLIC,
    )


_MINE_CHANNEL = OwnedChannel(id=_MINE, title="my channel", uploads_playlist="UUmine")


class Test_judge:
    """Given a video, when it is judged, then only two bases survive."""

    def test_allows_creative_commons_without_any_identity(self) -> None:
        verdict = judge(_video(License.CREATIVE_COMMONS), None)

        assert isinstance(verdict, Allowed)
        assert verdict.basis is RightsBasis.CREATIVE_COMMONS
        assert verdict.video.license is License.CREATIVE_COMMONS

    def test_allows_a_video_from_the_owned_channel(self) -> None:
        verdict = judge(_video(License.YOUTUBE, channel_id=_MINE), _MINE_CHANNEL)

        assert isinstance(verdict, Allowed)
        assert verdict.basis is RightsBasis.OWNED

    def test_allows_a_private_upload_from_the_owned_channel(self) -> None:
        video = Video(
            id=VideoId("dQw4w9WgXcQ"),
            title="a title",
            channel_id=_MINE,
            channel_title="my channel",
            license=License.YOUTUBE,
            privacy=PrivacyStatus.PRIVATE,
        )

        verdict = judge(video, _MINE_CHANNEL)

        assert isinstance(verdict, Allowed)
        assert verdict.basis is RightsBasis.OWNED

    def test_blocks_a_standard_licensed_video_from_a_stranger(self) -> None:
        verdict = judge(_video(License.YOUTUBE), _MINE_CHANNEL)

        assert isinstance(verdict, Refused)
        assert "youtube" in verdict.why
        assert "Creative Commons" in verdict.why

    def test_blocks_a_standard_video_when_no_channel_is_known(self) -> None:
        verdict = judge(_video(License.YOUTUBE), None)

        assert isinstance(verdict, Refused)

    def test_blocks_an_unlisted_video_belonging_to_someone_else(self) -> None:
        video = Video(
            id=VideoId("dQw4w9WgXcQ"),
            title="a title",
            channel_id=_OTHER,
            channel_title="their channel",
            license=License.YOUTUBE,
            privacy=PrivacyStatus.UNLISTED,
        )

        verdict = judge(video, _MINE_CHANNEL)

        assert isinstance(verdict, Refused)

    @pytest.mark.parametrize(
        ("license_", "owned"),
        [
            (License.CREATIVE_COMMONS, None),
            (License.CREATIVE_COMMONS, _MINE_CHANNEL),
            (License.YOUTUBE, _MINE_CHANNEL),
            (License.YOUTUBE, None),
        ],
    )
    def test_returns_one_of_the_two_variants(
        self, license_: License, owned: OwnedChannel | None
    ) -> None:
        verdict: Verdict = judge(_video(license_, _MINE), owned)

        assert type(verdict) in {Allowed, Refused}
