"""Rendering: every outcome variant produces one row, none is dropped."""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest

from ytmine.download import (
    Broken,
    DownloadOutcome,
    Planned,
    Saved,
    Unchanged,
)
from ytmine.gate import Allowed, Refused, RightsBasis
from ytmine.models import ChannelId, License, PrivacyStatus, Video, VideoId
from ytmine.report import outcome_row, render_outcome, render_verdict

_WHY: Final = "licenca 'youtube' nao e Creative Commons nem video seu"
_PATHS: Final = (Path("out/a.mp4"),)


@pytest.fixture
def video() -> Video:
    return Video(
        id=VideoId("dQw4w9WgXcQ"),
        title="a title",
        channel_id=ChannelId("UCother"),
        channel_title="their channel",
        license=License.YOUTUBE,
        privacy=PrivacyStatus.PUBLIC,
    )


def _outcomes(video: Video) -> list[DownloadOutcome]:
    return [
        Planned(video=video, basis=RightsBasis.CREATIVE_COMMONS),
        Saved(video=video, basis=RightsBasis.OWNED, paths=_PATHS),
        Unchanged(video=video),
        Broken(video=video, status=7),
        Refused(video=video, why=_WHY),
    ]


class Test_render_outcome:
    """Given every outcome variant, when it is rendered, then one row appears."""

    def test_renders_a_row_for_every_variant(self, video: Video) -> None:
        for outcome in _outcomes(video):
            row = outcome_row(outcome)

            assert row.title == "a title"
            assert row.status
            assert row.detail

    def test_names_the_files_a_saved_video_produced(self, video: Video) -> None:
        line = render_outcome(Saved(video=video, basis=RightsBasis.OWNED, paths=_PATHS))

        assert "a.mp4" in line
        assert "seu upload" in line

    def test_says_nothing_when_a_saved_video_produced_no_file(
        self, video: Video
    ) -> None:
        row = outcome_row(
            Saved(video=video, basis=RightsBasis.CREATIVE_COMMONS, paths=())
        )

        assert row.detail == "nenhum arquivo"


class Test_render_verdict:
    """Given a verdict, when it is rendered, then the reason is attached."""

    def test_marks_an_allowed_video_with_its_basis(self, video: Video) -> None:
        line = render_verdict(Allowed(video=video, basis=RightsBasis.CREATIVE_COMMONS))

        assert "permitido" in line

    def test_marks_a_refused_video_with_the_reason(self, video: Video) -> None:
        line = render_verdict(Refused(video=video, why=_WHY))

        assert "bloqueado" in line
        assert _WHY in line
