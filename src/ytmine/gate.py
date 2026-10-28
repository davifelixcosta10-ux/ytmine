"""The rights gate: the only two grounds on which ytmine downloads.

Everything else — every standard-licensed video that is not the user's own — is
refused here, before a single byte is requested. This module is pure so the
policy can be tested without touching the network.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum, unique

from ytmine.models import License, OwnedChannel, Video


@unique
class RightsBasis(StrEnum):
    """Why a download was permitted."""

    OWNED = "seu upload"
    CREATIVE_COMMONS = "licenca Creative Commons"


@dataclass(frozen=True, slots=True)
class Allowed:
    """The video may be downloaded."""

    video: Video
    basis: RightsBasis


@dataclass(frozen=True, slots=True)
class Refused:
    """The video may not be downloaded."""

    video: Video
    why: str


type Verdict = Allowed | Refused


def judge(video: Video, owned: OwnedChannel | None) -> Verdict:
    """Decide whether one video may be downloaded under the licence policy."""
    if video.license is License.CREATIVE_COMMONS:
        return Allowed(video=video, basis=RightsBasis.CREATIVE_COMMONS)
    if owned is not None and video.channel_id == owned.id:
        return Allowed(video=video, basis=RightsBasis.OWNED)
    return Refused(
        video=video,
        why=f"licenca '{video.license.value}' nao e Creative Commons nem video seu",
    )
