"""Boundary: API payloads become domain objects, errors become typed ones."""

from __future__ import annotations

import httpx2
import pytest

from ytmine.api import raise_api_error, to_license, to_privacy, to_video
from ytmine.errors import QuotaExceededError, YouTubeApiError
from ytmine.models import License, PrivacyStatus, VideoResource

_URL = "https://www.googleapis.com/youtube/v3/videos"


def _resource(license_: str, privacy: str = "public") -> VideoResource:
    """Build a valid API video resource for one licence and privacy value."""
    payload = (
        '{"id":"dQw4w9WgXcQ",'
        '"snippet":{"title":"a clip","channelId":"UCother",'
        '"channelTitle":"their channel"},'
        f'"status":{{"privacyStatus":"{privacy}","license":"{license_}"}}}}'
    )
    return VideoResource.model_validate_json(payload)


def _response(status: int, body: str) -> httpx2.Response:
    return httpx2.Response(
        status_code=status,
        text=body,
        request=httpx2.Request("GET", _URL),
    )


class Testto_video:
    """Given a video resource, when it is mapped, then the domain object is exact."""

    def test_maps_a_creative_commons_resource(self) -> None:
        video = to_video(_resource("creativeCommon"))

        assert video.id == "dQw4w9WgXcQ"
        assert video.title == "a clip"
        assert video.channel_title == "their channel"
        assert video.license is License.CREATIVE_COMMONS
        assert video.privacy is PrivacyStatus.PUBLIC
        assert video.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    def test_maps_the_standard_youtube_licence(self) -> None:
        assert to_video(_resource("youtube")).license is License.YOUTUBE

    @pytest.mark.parametrize("privacy", ["public", "unlisted", "private"])
    def test_maps_every_privacy_status(self, privacy: str) -> None:
        assert to_video(_resource("youtube", privacy=privacy)).privacy is PrivacyStatus(
            privacy
        )

    def test_an_unknown_licence_falls_back_to_youtubes_default(self) -> None:
        assert to_video(_resource("someNewLicence")).license is License.YOUTUBE

    def test_an_unknown_privacy_falls_back_to_private(self) -> None:
        assert (
            to_video(_resource("youtube", privacy="someNewStatus")).privacy
            is PrivacyStatus.PRIVATE
        )


class Testto_license:
    """Given a licence string, when it is mapped, then only CC is permissive."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("creativeCommon", License.CREATIVE_COMMONS),
            ("youtube", License.YOUTUBE),
            ("", License.YOUTUBE),
            ("creativeCommons", License.YOUTUBE),
        ],
    )
    def test_maps_known_and_unknown_values(self, raw: str, expected: License) -> None:
        assert to_license(raw) is expected


class Testto_privacy:
    """Given a privacy string, when it is mapped, then unknown means private."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("public", PrivacyStatus.PUBLIC),
            ("unlisted", PrivacyStatus.UNLISTED),
            ("private", PrivacyStatus.PRIVATE),
            ("", PrivacyStatus.PRIVATE),
        ],
    )
    def test_maps_known_and_unknown_values(
        self, raw: str, expected: PrivacyStatus
    ) -> None:
        assert to_privacy(raw) is expected


class Testraise_api_error:
    """Given a non-2xx response, when it is raised, then quota is a typed error."""

    @pytest.mark.parametrize(
        "reason", ["quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded"]
    )
    def test_turns_a_quota_403_into_quota_exceeded(self, reason: str) -> None:
        response = _response(403, f'{{"error":{{"errors":[{{"reason":"{reason}"}}]}}}}')

        with pytest.raises(QuotaExceededError) as raised:
            raise_api_error(response)

        assert reason in str(raised.value)

    def test_keeps_other_403s_as_plain_api_errors(self) -> None:
        response = _response(403, '{"error":{"errors":[{"reason":"forbidden"}]}}')

        with pytest.raises(YouTubeApiError) as raised:
            raise_api_error(response)

        assert raised.value.status == 403
        assert "forbidden" in raised.value.reason

    def test_keeps_a_404_as_a_plain_api_error(self) -> None:
        response = _response(404, '{"error":{"errors":[{"reason":"videoNotFound"}]}}')

        with pytest.raises(YouTubeApiError) as raised:
            raise_api_error(response)

        assert raised.value.status == 404

    def test_survives_an_unparseable_error_body(self) -> None:
        response = _response(500, "<html>gateway blew up</html>")

        with pytest.raises(YouTubeApiError) as raised:
            raise_api_error(response)

        assert raised.value.status == 500
        assert "gateway blew up" in raised.value.reason
