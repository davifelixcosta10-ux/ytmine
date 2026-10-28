"""OAuth token persistence and refresh for Google's loopback flow."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict

from ytmine.errors import AuthorizationError
from ytmine.http import create_async_client

_EXCHANGE_URL: Final = "https://oauth2.googleapis.com/token"
_REFRESH_SKEW: Final = 60.0
_OK: Final = 200
_FILE_MODE: Final = 0o600
_DIR_MODE: Final = 0o700


@dataclass(frozen=True, slots=True)
class Credentials:
    """A Google OAuth token pair plus the client that minted it."""

    access_token: str
    refresh_token: str
    expires_at: float
    client_id: str
    client_secret: str

    def expires_soon(self, now: float) -> bool:
        """True when the access token is inside the refresh skew window."""
        return now >= self.expires_at - _REFRESH_SKEW


class TokenPayload(BaseModel):
    """On-disk shape of a cached token."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str
    expires_at: float
    client_id: str
    client_secret: str


class TokenResponsePayload(BaseModel):
    """Subset of a Google token response that ytmine needs."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    access_token: str
    expires_in: int


def load(path: Path) -> Credentials | None:
    """Read a cached token, or ``None`` when nothing is cached yet."""
    if not path.is_file():
        return None
    payload = TokenPayload.model_validate_json(path.read_text(encoding="utf-8"))
    return Credentials(
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        expires_at=payload.expires_at,
        client_id=payload.client_id,
        client_secret=payload.client_secret,
    )


def save(path: Path, credentials: Credentials) -> None:
    """Persist a token with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=_FILE_MODE, exist_ok=True)
    payload = TokenPayload(
        access_token=credentials.access_token,
        refresh_token=credentials.refresh_token,
        expires_at=credentials.expires_at,
        client_id=credentials.client_id,
        client_secret=credentials.client_secret,
    )
    path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
    path.chmod(_FILE_MODE)
    path.parent.chmod(_DIR_MODE)


async def refresh(credentials: Credentials, now: float) -> Credentials:
    """Trade the refresh token for a new access token.

    Args:
        credentials: The stored credentials.
        now: Current epoch seconds, injected so callers stay deterministic.

    Raises:
        AuthorizationError: Google rejected the refresh token.
    """
    async with create_async_client() as client:
        response = await client.post(
            _EXCHANGE_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": credentials.refresh_token,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            },
        )
    if response.status_code != _OK:
        raise AuthorizationError(
            reason=f"refresh failed with {response.status_code}: {response.text[:200]}"
        )
    payload = TokenResponsePayload.model_validate_json(response.text)
    return replace(
        credentials,
        access_token=payload.access_token,
        expires_at=now + payload.expires_in,
    )


async def ensure_fresh(
    credentials: Credentials, now: float | None = None
) -> Credentials:
    """Return credentials with a live access token, refreshing when needed."""
    moment = time.time() if now is None else now
    if not credentials.expires_soon(moment):
        return credentials
    return await refresh(credentials, moment)


def clock() -> float:
    """Current epoch seconds."""
    return time.time()


__all__ = [
    "Credentials",
    "TokenPayload",
    "TokenResponsePayload",
    "clock",
    "ensure_fresh",
    "load",
    "refresh",
    "save",
]
