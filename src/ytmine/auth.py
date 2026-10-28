"""Google OAuth 2.0 for an 'Desktop app' client, copy-paste flavour.

Nothing listens on the loopback port: Google redirects there, the browser shows
an error page, and the user pastes the resulting URL back. That keeps the flow
thread-free and trivially testable — the prompt lives in the CLI, not here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from typing import ClassVar, Final
from urllib.parse import parse_qs, urlencode

from pydantic import BaseModel, ConfigDict

from ytmine.errors import AuthorizationError, ClientSecretsMissingError
from ytmine.http import create_async_client
from ytmine.token import Credentials

_SCOPES: Final = ("https://www.googleapis.com/auth/youtube.readonly",)
_AUTH_URL: Final = "https://accounts.google.com/o/oauth2/v2/auth"
_EXCHANGE_URL: Final = "https://oauth2.googleapis.com/token"
_DEFAULT_REDIRECT: Final = "http://127.0.0.1:53123"
_OK: Final = 200


@dataclass(frozen=True, slots=True)
class ClientSecrets:
    """The two values a Google OAuth client is made of."""

    client_id: str
    client_secret: str


class _DesktopClientPayload(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    client_id: str
    client_secret: str


class ClientSecretsFilePayload(BaseModel):
    """Google's downloaded OAuth client JSON, either flavour."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    installed: _DesktopClientPayload | None = None
    web: _DesktopClientPayload | None = None


class CodeExchangePayload(BaseModel):
    """Subset of a code-for-token exchange response."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    access_token: str
    refresh_token: str = ""
    expires_in: int


def redirect_uri() -> str:
    """The loopback URI Google redirects to; overridable per client config."""
    return os.environ.get("YTMINE_REDIRECT_URI", _DEFAULT_REDIRECT)


def read_client_secrets(path: Path) -> ClientSecrets:
    """Read the Google client JSON from ``path``.

    Raises:
        ClientSecretsMissingError: the file is absent.
        AuthorizationError: the file is not a downloadable OAuth client.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ClientSecretsMissingError(path=str(path)) from None
    payload = ClientSecretsFilePayload.model_validate_json(raw)
    section = payload.installed if payload.installed is not None else payload.web
    if section is None:
        raise AuthorizationError(
            reason=f"{path} carries neither an 'installed' nor a 'web' client"
        )
    return ClientSecrets(
        client_id=section.client_id, client_secret=section.client_secret
    )


def authorization_url(secrets: ClientSecrets, state: str) -> str:
    """Build the consent URL the user must visit."""
    params = {
        "client_id": secrets.client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def extract_code(pasted: str) -> str:
    """Pull the authorisation code out of a pasted URL, or pass a bare code through.

    Raises:
        AuthorizationError: a URL was pasted that carries no code, or Google refused.
    """
    text = pasted.strip()
    if not text.startswith(("http://", "https://")):
        return text
    separator = "?" if "?" in text else "#"
    values = parse_qs(text.split(separator, 1)[1])
    if "code" in values:
        return values["code"][0]
    if "error" in values:
        raise AuthorizationError(reason=f"Google recusou: {values['error'][0]}")
    raise AuthorizationError(reason="a URL colada nao carrega o parametro `code`")


async def exchange_code(code: str, secrets_: ClientSecrets, now: float) -> Credentials:
    """Trade an authorisation code for a token pair.

    Raises:
        AuthorizationError: Google rejected the exchange.
    """
    async with create_async_client() as client:
        response = await client.post(
            _EXCHANGE_URL,
            data={
                "code": code,
                "client_id": secrets_.client_id,
                "client_secret": secrets_.client_secret,
                "redirect_uri": redirect_uri(),
                "grant_type": "authorization_code",
            },
        )
    if response.status_code != _OK:
        raise AuthorizationError(
            reason=f"exchange failed with {response.status_code}: {response.text[:200]}"
        )
    payload = CodeExchangePayload.model_validate_json(response.text)
    return Credentials(
        access_token=payload.access_token,
        refresh_token=payload.refresh_token,
        expires_at=now + payload.expires_in,
        client_id=secrets_.client_id,
        client_secret=secrets_.client_secret,
    )


def new_state() -> str:
    """Fresh CSRF state for the consent round trip."""
    return token_urlsafe(16)


__all__ = [
    "ClientSecrets",
    "ClientSecretsFilePayload",
    "CodeExchangePayload",
    "authorization_url",
    "exchange_code",
    "extract_code",
    "new_state",
    "read_client_secrets",
    "redirect_uri",
]
